import { describe, expect, it } from "vitest";

import type { EndpointSetting } from "@/types";

import { keyLabel, testSummary, withTarget } from "./settings";

const LAN: EndpointSetting = { name: "lan", base_url: "http://127.0.0.1:10/v1", local: false, key_env: null, key: "missing", allow_typed_key: true, typed: false };

describe("an endpoint's key in the drawer (spec §5.3, §19.2)", () => {
  it("is shown by presence only, and a typed one only as entered for this session", () => {
    expect(keyLabel({ ...LAN, key: "present", typed: true })).toBe("key entered for this session");
    expect(keyLabel(LAN)).toBe("no key yet: type one below to use it this session");
    expect(keyLabel({ ...LAN, key_env: "SPARK_API_KEY", key: "present", allow_typed_key: false })).toBe("SPARK_API_KEY is set");
    expect(keyLabel({ ...LAN, key_env: "SPARK_API_KEY", allow_typed_key: false })).toBe("SPARK_API_KEY isn't set in the shell vid2sub started from");
    expect(keyLabel({ ...LAN, key: "none", allow_typed_key: false })).toBe("no key");
  });
});

describe("a Test's answer", () => {
  it("lists the models the server serves, or says why it failed", () => {
    expect(testSummary({ endpoint: "lan", n: 1, ok: true, models: ["w", "g"], more: 0, error: null })).toBe("Answers, serving w, g");
    expect(testSummary({ endpoint: "lan", n: 1, ok: true, models: ["w"], more: 3, error: null })).toBe("Answers, serving w and 3 more");
    expect(testSummary({ endpoint: "lan", n: 1, ok: true, models: [], more: 0, error: null })).toBe("Answers, serving no models");
    expect(testSummary({ endpoint: "lan", n: 1, ok: false, models: [], more: 0, error: "couldn't reach the server" })).toBe("couldn't reach the server");
  });
});

describe("the session's targets", () => {
  it("keep the drawer's order, and never become none", () => {
    const order = ["en", "ja", "ko"];
    expect(withTarget(["en"], "ja", true, order)).toEqual(["en", "ja"]);
    expect(withTarget(["ja"], "en", true, order)).toEqual(["en", "ja"]);
    expect(withTarget(["en", "ja"], "en", false, order)).toEqual(["ja"]);
    expect(withTarget(["en"], "en", false, order)).toEqual(["en"]);
  });
});
