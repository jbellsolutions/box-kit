// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package store

import (
	"context"
	"path/filepath"
	"testing"
	"time"

	"browser-box-pp-cli/internal/ledger"
)

func openTemp(t *testing.T) *Store {
	t.Helper()
	s, err := OpenWithContext(context.Background(), filepath.Join(t.TempDir(), "data.db"))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { s.Close() })
	return s
}

func record(t *testing.T, s *Store, tool, req, resp string, status int, at time.Time) {
	t.Helper()
	call, page := ledger.Build(tool, []byte(req), []byte(resp), status, time.Second, at)
	var snap []byte
	if tool == "status" && call.OK {
		snap = []byte(resp)
	}
	if err := s.RecordCall(context.Background(), call, page, snap); err != nil {
		t.Fatal(err)
	}
}

func TestLedgerRoundTrip(t *testing.T) {
	s := openTemp(t)
	ctx := context.Background()
	old := time.Now().Add(-10 * 24 * time.Hour)
	record(t, s, "read", `{"url":"https://example.com"}`, `{"title":"Example Domain","final_url":"https://example.com/","text":"Pricing starts at ten dollars"}`, 200, old)
	record(t, s, "read", `{"url":"http://127.0.0.1"}`, `{"error":"refused: loopback"}`, 422, time.Now())
	record(t, s, "task", `{"goal":"top story"}`, `{"status":"done","estimated_cost_usd":0.004}`, 200, time.Now())

	all, err := s.Calls(ctx, CallFilter{})
	if err != nil || len(all) != 3 {
		t.Fatalf("calls = %d, %v", len(all), err)
	}
	if all[0].Tool != "task" || all[0].CostUSD == nil {
		t.Errorf("newest first with cost: %+v", all[0])
	}
	failed, _ := s.Calls(ctx, CallFilter{Status: "failed"})
	if len(failed) != 1 || failed[0].Status != "refused" {
		t.Errorf("failed = %+v", failed)
	}
	recent, _ := s.Calls(ctx, CallFilter{Since: time.Now().Add(-24 * time.Hour)})
	if len(recent) != 2 {
		t.Errorf("since 24h = %d, want 2", len(recent))
	}
	reads, _ := s.Calls(ctx, CallFilter{Tool: "read", Limit: 1})
	if len(reads) != 1 || reads[0].Tool != "read" {
		t.Errorf("tool filter/limit = %+v", reads)
	}
}

func TestPageCacheAndSearch(t *testing.T) {
	s := openTemp(t)
	ctx := context.Background()
	record(t, s, "read", `{"url":"https://example.com"}`, `{"title":"Example Domain","final_url":"https://example.com/","text":"Pricing starts at ten dollars"}`, 200, time.Now())
	record(t, s, "fetch", `{"url":"https://news.ycombinator.com"}`, `{"final_url":"https://news.ycombinator.com/","text":"Hacker News front page"}`, 200, time.Now())

	for _, u := range []string{"https://example.com", "https://example.com/"} {
		p, err := s.LatestPage(ctx, u)
		if err != nil || p == nil || p.Title != "Example Domain" {
			t.Fatalf("LatestPage(%s) = %+v, %v", u, p, err)
		}
	}
	missing, err := s.LatestPage(ctx, "https://nowhere.example")
	if err != nil || missing != nil {
		t.Fatalf("missing page = %+v, %v", missing, err)
	}

	hits, err := s.SearchPages(ctx, "pricing", 10)
	if err != nil || len(hits) != 1 || hits[0].URL != "https://example.com" {
		t.Fatalf("hits = %+v, %v", hits, err)
	}
	none, err := s.SearchPages(ctx, "kubernetes", 10)
	if err != nil || len(none) != 0 {
		t.Fatalf("negative query matched: %+v, %v", none, err)
	}
	odd, err := s.SearchPages(ctx, `pricing" OR (`, 10)
	if err != nil {
		t.Fatalf("punctuation broke the query: %v", err)
	}
	_ = odd
	pages, _ := s.Pages(ctx, 10)
	if len(pages) != 2 {
		t.Errorf("pages = %d", len(pages))
	}
}

func TestSnapshotsAndAliases(t *testing.T) {
	s := openTemp(t)
	ctx := context.Background()
	if snap, err := s.LatestSnapshot(ctx); err != nil || snap != nil {
		t.Fatalf("empty store snapshot = %+v, %v", snap, err)
	}
	record(t, s, "status", ``, `{"browser_lane":"free"}`, 200, time.Now())
	snap, err := s.LatestSnapshot(ctx)
	if err != nil || snap == nil || string(snap.Data) != `{"browser_lane":"free"}` {
		t.Fatalf("snapshot = %+v, %v", snap, err)
	}

	record(t, s, "session", `{"action":"create"}`, `{"session_id":"sess_1"}`, 200, time.Now())
	record(t, s, "session", `{"action":"create"}`, `{"session_id":"sess_2"}`, 200, time.Now())
	last, err := s.LastCreatedSession(ctx)
	if err != nil || last != "sess_2" {
		t.Fatalf("last session = %q, %v", last, err)
	}
	if err := s.SetAlias(ctx, Alias{Name: "crm", SessionID: "sess_1", UpdatedAt: "t1"}); err != nil {
		t.Fatal(err)
	}
	if err := s.SetAlias(ctx, Alias{Name: "crm", SessionID: "sess_2", UpdatedAt: "t2"}); err != nil {
		t.Fatal(err)
	}
	a, _ := s.GetAlias(ctx, "crm")
	if a == nil || a.SessionID != "sess_2" {
		t.Fatalf("alias = %+v", a)
	}
	list, _ := s.Aliases(ctx)
	if len(list) != 1 {
		t.Fatalf("aliases = %+v", list)
	}
	gone, _ := s.DeleteAlias(ctx, "crm")
	again, _ := s.DeleteAlias(ctx, "crm")
	if !gone || again {
		t.Fatalf("delete = %v then %v", gone, again)
	}
}
