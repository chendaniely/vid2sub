# Contracts with recordings

vid2sub's transcript renditions use recordings' `recordings/rendition@1` envelope and its
`TranscriptPayload` exactly (spec §14.3), so recordings can import them. These schemas are copies
from recordings at commit `64b75513876207f6e4d0ddfd7191497551c6e200`. When recordings changes its
rendition format, copy the new schema here (with its commit) and re-run `tests/test_rendition.py`.
