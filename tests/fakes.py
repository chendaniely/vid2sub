"""Test doubles on real sockets, as recordings does: the code under test makes real HTTP calls."""

from __future__ import annotations

import json
import re
import socket
import threading
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from vid2sub.engines.base import ChunkResult, ModelStamp
from vid2sub.parse import ParsedChunk
from vid2sub.subs.model import Segment, Word


@dataclass
class Request:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes

    def form(self) -> dict[str, tuple[str | None, bytes]]:
        ctype = self.headers["content-type"]
        message = BytesParser(policy=policy.HTTP).parsebytes(
            b"Content-Type: " + ctype.encode() + b"\r\n\r\n" + self.body)
        out = {}
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")
            out[name] = (part.get_filename(), part.get_payload(decode=True))
        return out

    def json(self):
        return json.loads(self.body)


class FakeServer:
    """Scripted responses `(status, json-or-bytes, headers)`, or a `responder(request)`."""

    def __init__(self, responses=None, responder=None):
        self.requests: list[Request] = []
        self.responses = list(responses or [])
        self.responder = responder
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _respond(self):
                length = int(self.headers.get("content-length") or 0)
                req = Request(self.command, self.path,
                              {k.lower(): v for k, v in self.headers.items()},
                              self.rfile.read(length))
                server.requests.append(req)
                if server.responder is not None:
                    status, payload, headers = server.responder(req)
                elif server.responses:
                    status, payload, headers = server.responses.pop(0)
                else:
                    status, payload, headers = 200, {}, {}
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = _respond

        return Handler


def closed_port_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}/v1"


def _schema_ids(node):
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "src" in props:
            items = props["src"].get("items", {})
            return items.get("enum") or ([items["const"]] if "const" in items else [])
        for value in node.values():
            found = _schema_ids(value)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _schema_ids(value)
            if found:
                return found
    return []


def chat_responder(req):
    """An OpenAI-compatible chat completion that fills the request's batch schema."""
    body = req.json()
    ids = _schema_ids(body["response_format"]["json_schema"]["schema"])
    content = json.dumps({"items": [{"src": [i], "text": f"EN {i}"} for i in ids]})
    return 200, {
        "id": "chatcmpl-test", "object": "chat.completion", "created": 0, "model": body["model"],
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }, {}


class FakeEngine:
    """A transcription engine that hears one word every 500 ms of each chunk."""

    max_chunk_s = 300.0
    supports_prompt = True

    def __init__(self, name="whisper.cpp", language="ja", detect=None, fail=None, text=None):
        self.name = name
        self.language = language
        self.detect = detect if detect is not None else {language: 0.95}
        self.fail = list(fail or [])
        self.text = text or ("字" if language in ("ja", "zh", "yue") else " word")
        self.calls: list[tuple] = []

    def transcribe(self, chunk, *, language, prompt):
        self.calls.append(("transcribe", chunk.index, language, prompt))
        if self.fail:
            raise self.fail.pop(0)
        words = tuple(Word(text=self.text, start_ms=t, end_ms=t + 300)
                      for t in range(200, max(chunk.duration_ms - 400, 201), 500))
        if not words:
            return ChunkResult(ParsedChunk((), language, {}))
        seg = Segment(text="".join(w.text for w in words), start_ms=words[0].start_ms,
                      end_ms=words[-1].end_ms, words=words)
        return ChunkResult(ParsedChunk((seg,), language or self.language, {self.language: 0.95}))

    def detect_language(self, chunk):
        self.calls.append(("detect", chunk.index))
        if isinstance(self.detect, list):
            return dict(self.detect.pop(0))
        return dict(self.detect)

    def stamp(self):
        return ModelStamp(self.name, "fake-model", "unknown")

    def close(self):
        pass


def fake_make_ask(*args, **kwargs):
    """Stands in for translate.run.make_ask: 'EN <id>' for every cue it's asked about."""
    def ask(system, prompt, model):
        ids = re.findall(r"^\[(\S+)\] \(max", prompt, flags=re.MULTILINE)
        return model.model_validate({"items": [{"src": [i], "text": f"EN {i}"} for i in ids]})
    return ask
