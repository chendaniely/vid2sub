"""The sidecar next to a video: an append-only JSON Lines file (spec §14).

Line 1 is a header; every other line is one immutable record. A merge of two writers is the union
of their records, so nothing is ever lost. Rendition ids are hashes of their content. Each track's
current version is named by head records; a head record says which head it replaces, so the
current head is the one nothing replaced, and two of those mean two writers diverged: a conflict
the user resolves (plan decision 4). A truncated last line (a crash mid-write) is ignored and
reported; any other unreadable line stops everything, because vid2sub never overwrites a sidecar
it can't read (spec §14.6). Paths are basenames only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

SIDECAR_SCHEMA = "vid2sub/sidecar@1"
HeadBy = Literal["auto", "editor", "external", "import", "user"]


class _Rec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class VideoInfo(_Rec):
    name: str
    size: int
    quick_sha256: str
    duration_ms: int


class Header(_Rec):
    schema_: Literal["vid2sub/sidecar@1"] = Field(default=SIDECAR_SCHEMA, alias="schema")
    video: VideoInfo


class IdentityRecord(_Rec):
    type: Literal["identity"] = "identity"
    sha256: str
    at: str


class RenditionRecord(_Rec):
    type: Literal["rendition"] = "rendition"
    id: str
    parents: tuple[str, ...] = ()
    track: str | None
    body: dict[str, Any]


class HeadRecord(_Rec):
    type: Literal["head"] = "head"
    track: str
    rendition: str
    replaces: str | None = None
    by: HeadBy
    at: str


class ProjectionRecord(_Rec):
    type: Literal["projection"] = "projection"
    path: str
    format: Literal["srt", "ass"]
    track: str
    rendition: str
    sha256: str
    at: str


Record = Annotated[IdentityRecord | RenditionRecord | HeadRecord | ProjectionRecord,
                   Field(discriminator="type")]
_RECORD: TypeAdapter[Record] = TypeAdapter(Record)


class SidecarError(ValueError):
    pass


@dataclass(frozen=True)
class Conflict:
    track: str
    leaves: tuple[str, ...]


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dump(rec: BaseModel) -> dict[str, Any]:
    return rec.model_dump(mode="json", by_alias=True)


def make_rendition(parents: Sequence[str], track: str | None,
                   body: dict[str, Any]) -> RenditionRecord:
    content = {"type": "rendition", "parents": list(parents), "track": track, "body": body}
    rid = "r_" + hashlib.sha256(canonical_json(content).encode()).hexdigest()[:16]
    return RenditionRecord(id=rid, parents=tuple(parents), track=track, body=body)


@dataclass(frozen=True)
class Sidecar:
    header: Header
    records: tuple[Any, ...] = field(default_factory=tuple)

    def add(self, *records: Any) -> Sidecar:
        seen = {canonical_json(_dump(r)) for r in self.records}
        new = list(self.records)
        for r in records:
            key = canonical_json(_dump(r))
            if key not in seen:
                seen.add(key)
                new.append(r)
        return Sidecar(self.header, tuple(new))

    def renditions(self) -> dict[str, RenditionRecord]:
        return {r.id: r for r in self.records if isinstance(r, RenditionRecord)}

    def transcripts(self) -> list[RenditionRecord]:
        return [r for r in self.records
                if isinstance(r, RenditionRecord) and r.body.get("kind") == "transcript"]

    def heads(self, track: str) -> list[HeadRecord]:
        return [r for r in self.records if isinstance(r, HeadRecord) and r.track == track]

    def head(self, track: str) -> HeadRecord | Conflict | None:
        heads = self.heads(track)
        if not heads:
            return None
        replaced = {h.replaces for h in heads if h.replaces}
        leaves: dict[str, HeadRecord] = {}
        for h in heads:
            if h.rendition not in replaced:
                leaves[h.rendition] = h
        if not leaves:  # a replacement cycle: no head is current, so don't guess by file order
            return Conflict(track, tuple(sorted({h.rendition for h in heads})))
        if len(leaves) == 1:
            return next(iter(leaves.values()))
        return Conflict(track, tuple(leaves))

    def tracks(self) -> list[str]:
        out: list[str] = []
        for r in self.records:
            if isinstance(r, HeadRecord) and r.track not in out:
                out.append(r.track)
        return out

    def projections(self) -> dict[str, ProjectionRecord]:
        out: dict[str, ProjectionRecord] = {}
        for r in self.records:
            if isinstance(r, ProjectionRecord):
                out[r.path] = r
        return out

    def identity(self) -> str | None:
        found = [r.sha256 for r in self.records if isinstance(r, IdentityRecord)]
        return found[-1] if found else None


def parse_sidecar(text: str) -> tuple[Sidecar, list[str]]:
    warnings: list[str] = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    elif lines:
        try:
            json.loads(lines[-1])
        except ValueError:
            warnings.append("ignored a truncated last line")
            lines.pop()
    if not lines:
        raise SidecarError("the sidecar is empty")
    try:
        header = Header.model_validate(json.loads(lines[0]))
    except (ValueError, ValidationError):
        raise SidecarError("line 1 isn't a vid2sub sidecar header; refusing to write over it") \
            from None
    records = []
    for number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            records.append(_RECORD.validate_python(json.loads(line)))
        except (ValueError, ValidationError):
            raise SidecarError(f"line {number} isn't a vid2sub record; refusing to write over a "
                               "sidecar vid2sub can't read") from None
    return Sidecar(header, tuple(records)), warnings


def serialize(sidecar: Sidecar) -> str:
    lines = [canonical_json(_dump(sidecar.header))]
    lines += [canonical_json(_dump(r)) for r in sidecar.records]
    return "\n".join(lines) + "\n"
