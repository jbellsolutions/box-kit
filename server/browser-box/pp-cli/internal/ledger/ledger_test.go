// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package ledger

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestToolFromPath(t *testing.T) {
	cases := []struct {
		method, path, want string
		ok                 bool
	}{
		{"POST", "/api/v1/read", "read", true},
		{"POST", "/api/v1/task/", "task", true},
		{"GET", "/api/v1/status", "status", true},
		{"GET", "/api/v1/tools", "tools", true},
		{"POST", "/api/v1/status", "", false},
		{"GET", "/api/v1/read", "", false},
		{"GET", "/openapi.json", "", false},
		{"POST", "/api/v1/a/b", "", false},
		{"POST", "/api/v1/", "", false},
	}
	for _, c := range cases {
		got, ok := ToolFromPath(c.method, c.path)
		if got != c.want || ok != c.ok {
			t.Errorf("ToolFromPath(%s %s) = %q,%v want %q,%v", c.method, c.path, got, ok, c.want, c.ok)
		}
	}
}

func TestBuildReadKeepsThePage(t *testing.T) {
	at := time.Date(2026, 9, 23, 12, 0, 0, 0, time.UTC)
	call, page := Build("read",
		[]byte(`{"url":"https://example.com"}`),
		[]byte(`{"title":"Example Domain","final_url":"https://example.com/","text":"This domain is for use in examples.","links":["https://iana.org/domains/example"],"status_code":200}`),
		200, 1500*time.Millisecond, at)
	if !call.OK || call.Status != "ok" || call.Summary != "https://example.com" || call.DurationMS != 1500 {
		t.Fatalf("call = %+v", call)
	}
	if call.URL != "https://example.com" {
		t.Errorf("url = %q", call.URL)
	}
	if page == nil {
		t.Fatal("a successful read must yield a page")
	}
	if page.Title != "Example Domain" || page.FinalURL != "https://example.com/" || len(page.Links) != 1 || page.Via != "read" {
		t.Errorf("page = %+v", page)
	}
}

func TestBuildRefusalIsRecordedWithoutAPage(t *testing.T) {
	call, page := Build("read", []byte(`{"url":"http://127.0.0.1"}`),
		[]byte(`{"error":"refused: loopback address","tool":"read"}`), 422, time.Second, time.Now())
	if call.OK || call.Status != "refused" || !strings.Contains(call.Error, "loopback") {
		t.Fatalf("call = %+v", call)
	}
	if page != nil {
		t.Fatal("a refused read must not produce a page")
	}
}

func TestBuildLaneBusy(t *testing.T) {
	call, _ := Build("read", []byte(`{"url":"https://example.com"}`),
		[]byte(`{"error":"another job has held the browser lane for longer than 120s (task pid=7)"}`), 422, time.Second, time.Now())
	if call.Status != "lane_busy" {
		t.Fatalf("status = %q, want lane_busy", call.Status)
	}
}

func TestBuildTaskCostAndStatus(t *testing.T) {
	call, page := Build("task", []byte(`{"goal":"find the top story"}`),
		[]byte(`{"status":"done","answer":"x","estimated_cost_usd":0.0042}`), 200, time.Second, time.Now())
	if call.Status != "done" || call.CostUSD == nil || *call.CostUSD != 0.0042 || page != nil {
		t.Fatalf("call = %+v page=%v", call, page)
	}
	if call.Summary != "find the top story" {
		t.Errorf("summary = %q", call.Summary)
	}
}

func TestBuildSessionCreateKeepsTheID(t *testing.T) {
	call, _ := Build("session", []byte(`{"action":"create"}`), []byte(`{"session_id":"sess_42"}`), 200, 0, time.Now())
	if call.SessionID != "sess_42" || call.Summary != "create" {
		t.Fatalf("call = %+v", call)
	}
}

func TestComputerTypedTextIsRedacted(t *testing.T) {
	call, _ := Build("computer", []byte(`{"action":"type","text":"hunter2"}`), []byte(`{"ok":true}`), 200, 0, time.Now())
	if strings.Contains(string(call.Args), "hunter2") {
		t.Fatalf("typed text leaked into the ledger: %s", call.Args)
	}
	if call.Summary != "type" {
		t.Errorf("summary = %q", call.Summary)
	}
}

func TestFetchWithEmptyTextStoresNoPage(t *testing.T) {
	_, page := Build("fetch", []byte(`{"url":"https://example.com/x"}`), []byte(`{"status_code":204,"text":"   "}`), 200, 0, time.Now())
	if page != nil {
		t.Fatal("blank text is not a page")
	}
}

func TestWithoutScreenshot(t *testing.T) {
	out := WithoutScreenshot([]byte(`{"title":"t","screenshot_base64":"AAAA"}`))
	var m map[string]any
	if err := json.Unmarshal(out, &m); err != nil {
		t.Fatal(err)
	}
	if _, has := m["screenshot_base64"]; has || m["title"] != "t" {
		t.Fatalf("got %s", out)
	}
	same := []byte(`{"title":"t"}`)
	if string(WithoutScreenshot(same)) != string(same) {
		t.Fatal("a body without a screenshot must come back unchanged")
	}
}

func TestIsLaneBusy(t *testing.T) {
	for msg, want := range map[string]bool{
		"another job has held the browser lane for longer than 120s": true,
		"busy — one browser runs at a time":                          false,
		"lane busy":                                                  true,
		"session s-1 is busy (another call is using its browser); try again shortly": true,
		"refused: private address": false,
	} {
		if got := IsLaneBusy(msg); got != want {
			t.Errorf("IsLaneBusy(%q) = %v want %v", msg, got, want)
		}
	}
}

const statusA = `{"components":[{"name":"steel (the browser)","up":true},{"name":"orgo (computers, off-box)","up":false,"configured":false}],
"browser_lane":"free","tools_working_now":["fetch","read","status"],"tools_unavailable":[],"recent_calls":[{"tool":"read"}]}`

func TestDiffStatusNoChangeIsEmpty(t *testing.T) {
	// recent_calls differ, which must not count as drift
	b := strings.Replace(statusA, `[{"tool":"read"}]`, `[{"tool":"fetch"},{"tool":"read"}]`, 1)
	if got := DiffStatus([]byte(statusA), []byte(b)); len(got) != 0 {
		t.Fatalf("expected no drift, got %+v", got)
	}
}

func TestDiffStatusReportsWhatChanged(t *testing.T) {
	b := `{"components":[{"name":"steel (the browser)","up":false},{"name":"orgo (computers, off-box)","up":false,"configured":false}],
"browser_lane":"busy — one browser runs at a time on this host","tools_working_now":["fetch","status"],
"tools_unavailable":[{"tool":"read","reason":"steel is down"}]}`
	got := DiffStatus([]byte(statusA), []byte(b))
	want := map[string]Change{
		"component steel (the browser)": {Before: "up", After: "down"},
		"tool read":                     {Before: "working", After: "not working"},
		"unavailable read":              {Before: "(absent)", After: "steel is down"},
		"browser lane":                  {Before: "free", After: "busy"},
	}
	if len(got) != len(want) {
		t.Fatalf("got %d changes %+v, want %d", len(got), got, len(want))
	}
	for _, c := range got {
		w, ok := want[c.What]
		if !ok || w.Before != c.Before || w.After != c.After {
			t.Errorf("unexpected change %+v", c)
		}
	}
}

func TestDiffStatusGarbageIsEmpty(t *testing.T) {
	if got := DiffStatus([]byte("not json"), nil); len(got) != 0 {
		t.Fatalf("got %+v", got)
	}
}

func TestReportedFailuresAreNotOK(t *testing.T) {
	for _, resp := range []string{`{"status":"failed"}`, `{"status":"timed_out"}`, `{"ok":false,"detail":"x"}`, `{"status":"stopped"}`} {
		if call, _ := Build("act", []byte(`{"command":"click x"}`), []byte(resp), 200, 0, time.Now()); call.OK {
			t.Errorf("%s recorded as ok", resp)
		}
	}
	for _, resp := range []string{`{"status":"needs_confirmation"}`, `{"status":"done"}`, `{"ok":true}`} {
		if call, _ := Build("act", []byte(`{"command":"click x"}`), []byte(resp), 200, 0, time.Now()); !call.OK {
			t.Errorf("%s recorded as failed", resp)
		}
	}
}

func TestToolFromPathUnderAPrefix(t *testing.T) {
	if tool, ok := ToolFromPath("POST", "/box/api/v1/read"); !ok || tool != "read" {
		t.Fatalf("got %q %v", tool, ok)
	}
}
