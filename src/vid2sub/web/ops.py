"""The edits the editor sends, as typed values checked at the door (spec §20, §6.3).

Every edit arrives from the browser, so it is untrusted until `parse_op` has checked it: one
pydantic model per kind, discriminated on `op`, with unknown fields refused (`extra="forbid"`)
and nothing coerced (`strict`), so a string never becomes a number. Bounds keep a hostile page
from handing the server work or text it can't save: text up to 2,000 characters with no control
characters but line breaks and tabs and no lone surrogates (they can't be written as UTF-8),
times from 0 to 48 hours, cue ids in the shape `model.new_cue_id` makes, tracks only the keys
vid2sub knows. An edit that makes cues (split, merge, insert) carries their new ids, drawn by the
page, so a crash draft replays exactly (the Phase 2 plan's Decision 31); `subs.edit` refuses one
that is taken. `BadOp` names the field and why, never the value or an unknown field's name, so
nothing the page sent comes back in a message or a log (spec §6.8); pydantic's own error, which
quotes the input, is dropped. Each kind maps to one `subs.edit` operation; `glossary_add` is held
until Save writes the glossary (the Phase 2 plan's Decision 5).
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from vid2sub.subs import naming
from vid2sub.subs.edit import SOURCE

MAX_MS = 48 * 60 * 60 * 1000
MAX_TEXT = 2000
MAX_TERM = 200
_ALLOWED_CONTROLS = frozenset("\n\r\t")


def _saveable(text: str) -> str:
    for ch in text:
        category = unicodedata.category(ch)
        if category == "Cs" or (category == "Cc" and ch not in _ALLOWED_CONTROLS):
            raise ValueError("a character that can't be saved")
    return text


def _one_line(text: str) -> str:
    if not text.strip() or "\n" in text or "\r" in text:
        raise ValueError("one line of text")
    return _saveable(text)


CueId = Annotated[str, StringConstraints(pattern=r"^c[0-9a-f]{8}$")]
Ms = Annotated[int, Field(ge=0, le=MAX_MS)]
Delta = Annotated[int, Field(ge=-MAX_MS, le=MAX_MS)]
Text = Annotated[str, Field(max_length=MAX_TEXT), AfterValidator(_saveable)]
Find = Annotated[str, Field(min_length=1, max_length=MAX_TEXT), AfterValidator(_saveable)]
Term = Annotated[str, Field(min_length=1, max_length=MAX_TERM), AfterValidator(_one_line)]
Track = Literal[tuple(naming.TRACKS)]  # type: ignore[valid-type]
TrackOrSource = Literal[(SOURCE, *naming.TRACKS)]  # type: ignore[valid-type]


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SetText(_Op):
    op: Literal["set_text"] = "set_text"
    cue: CueId
    text: Text


class SetTranslationText(_Op):
    op: Literal["set_translation_text"] = "set_translation_text"
    track: Track
    cue: CueId
    text: Text


class SetTimes(_Op):
    op: Literal["set_times"] = "set_times"
    cue: CueId
    start_ms: Ms | None = None
    end_ms: Ms | None = None

    @model_validator(mode="after")
    def _an_edge(self) -> SetTimes:
        if self.start_ms is None and self.end_ms is None:
            raise ValueError("a start or an end")
        return self


class Nudge(_Op):
    op: Literal["nudge"] = "nudge"
    cue: CueId
    delta_ms: Delta
    edge: Literal["start", "end", "both"] = "both"


class Split(_Op):
    op: Literal["split"] = "split"
    cue: CueId
    at_char: Annotated[int, Field(ge=0, le=MAX_TEXT)]
    at_ms: Ms
    ids: Annotated[list[CueId], Field(min_length=2, max_length=2)]  # the two halves' new ids


class MergeNext(_Op):
    op: Literal["merge_next"] = "merge_next"
    cue: CueId
    id: CueId  # the merged cue's
    # per translation track, the id of the cue that joins its translations of the two parts
    joined: Annotated[dict[Track, CueId], Field(max_length=len(naming.TRACKS))]


class Insert(_Op):
    op: Literal["insert"] = "insert"
    start_ms: Ms
    end_ms: Ms
    text: Text
    id: CueId


class Delete(_Op):
    op: Literal["delete"] = "delete"
    cue: CueId


class Detach(_Op):
    op: Literal["detach"] = "detach"
    track: Track
    cue: CueId
    detached: bool


class ReplaceAll(_Op):
    op: Literal["replace_all"] = "replace_all"
    find: Find
    replace: Text
    tracks: Annotated[list[TrackOrSource], Field(min_length=1, max_length=len(naming.TRACKS) + 1)]


class GlossaryAdd(_Op):
    op: Literal["glossary_add"] = "glossary_add"
    term: Term
    translation: Term


EDIT_KINDS = (SetText, SetTranslationText, SetTimes, Nudge, Split, MergeNext, Insert, Delete,
              Detach, ReplaceAll, GlossaryAdd)
EditOp = Annotated[SetText | SetTranslationText | SetTimes | Nudge | Split | MergeNext | Insert
                   | Delete | Detach | ReplaceAll | GlossaryAdd, Field(discriminator="op")]
_ADAPTER: TypeAdapter[EditOp] = TypeAdapter(EditOp)

_REASONS = {
    "missing": "is missing",
    "union_tag_not_found": "is missing",
    "union_tag_invalid": "isn't a known edit",
    "string_too_long": "is too long",
    "string_too_short": "is too short",
    "greater_than_equal": "is out of range",
    "less_than_equal": "is out of range",
    "literal_error": "isn't one of the choices",
    "too_short": "has the wrong number of items",
    "too_long": "has the wrong number of items",
    "int_type": "has the wrong type",
    "string_type": "has the wrong type",
    "bool_type": "has the wrong type",
    "list_type": "has the wrong type",
    "dict_type": "has the wrong type",
}


class BadOp(ValueError):
    """An edit that doesn't pass; the message names the field, never what was sent."""

    def __init__(self, field: str | None, reason: str):
        self.field = field
        super().__init__(f"this edit can't be made: {reason}" if field is None
                         else f"this edit can't be made: {field} {reason}")


def parse_op(data: object) -> EditOp:
    if not isinstance(data, dict):
        raise BadOp(None, "an edit is a JSON object")
    try:
        return _ADAPTER.validate_python(data)
    except ValidationError as err:
        first = err.errors(include_url=False, include_context=False, include_input=False)[0]
    kind = first["type"]
    if kind == "extra_forbidden":
        raise BadOp(None, "it has a field no edit has")
    if kind in ("union_tag_invalid", "union_tag_not_found"):
        raise BadOp("op", _REASONS[kind])
    names = [part for part in first["loc"][1:] if isinstance(part, str)]
    raise BadOp(names[0] if names else str(first["loc"][0]), _REASONS.get(kind, "isn't valid"))
