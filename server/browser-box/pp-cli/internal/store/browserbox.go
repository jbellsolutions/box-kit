// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
	"time"

	"browser-box-pp-cli/internal/ledger"
)

// CallRow is one ledger row as history returns it.
type CallRow struct {
	ID         int64           `json:"id"`
	At         string          `json:"at"`
	Tool       string          `json:"tool"`
	Summary    string          `json:"summary"`
	Status     string          `json:"status"`
	OK         bool            `json:"ok"`
	HTTPStatus int             `json:"http_status"`
	Error      string          `json:"error,omitempty"`
	DurationMS int64           `json:"duration_ms"`
	CostUSD    *float64        `json:"cost_usd,omitempty"`
	SessionID  string          `json:"session_id,omitempty"`
	URL        string          `json:"url,omitempty"`
	Args       json.RawMessage `json:"args,omitempty"`
}

// PageRow is a cached page.
type PageRow struct {
	URL       string   `json:"url"`
	FinalURL  string   `json:"final_url"`
	Title     string   `json:"title"`
	Text      string   `json:"text,omitempty"`
	Links     []string `json:"links,omitempty"`
	Via       string   `json:"via"`
	FetchedAt string   `json:"fetched_at"`
	Snippet   string   `json:"snippet,omitempty"`
}

// Snapshot is one stored status result.
type Snapshot struct {
	At   string
	Data json.RawMessage
}

// Alias names a browser session.
type Alias struct {
	Name      string `json:"name"`
	SessionID string `json:"session_id"`
	Note      string `json:"note,omitempty"`
	UpdatedAt string `json:"updated_at"`
}

// RecordCall writes one call, the page it returned and, for status, a
// snapshot, in one transaction. A browser call that carries no session id is
// tagged with the session this ledger last saw created and not yet released:
// read, act and task use the open session's cookies without naming it.
func (s *Store) RecordCall(ctx context.Context, call ledger.Call, page *ledger.Page, snapshot json.RawMessage) (err error) {
	at := call.At.UTC().Format(ledger.TimeFormat)
	var cost any
	if call.CostUSD != nil {
		cost = *call.CostUSD
	}
	args := string(call.Args)
	if args == "" {
		args = "{}"
	}

	s.lockForWrite()
	defer s.unlockAfterWrite()
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() {
		if err != nil {
			_ = tx.Rollback()
		}
	}()
	sessionID := call.SessionID
	if sessionID == "" && ledger.UsesBrowserSession(call.Tool) {
		if sessionID, err = openSession(ctx, tx); err != nil {
			return err
		}
	}
	if _, err = tx.ExecContext(ctx, `INSERT INTO bb_calls
		(at, tool, summary, args, http_status, ok, status, error, duration_ms, cost_usd, session_id, url)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
		at, call.Tool, call.Summary, args, call.HTTPStatus, boolInt(call.OK), call.Status, call.Error,
		call.DurationMS, cost, sessionID, call.URL); err != nil {
		return err
	}
	if page != nil {
		links, _ := json.Marshal(page.Links)
		res, err := tx.ExecContext(ctx, `INSERT INTO bb_pages (url, final_url, title, text, links, via, fetched_at)
			VALUES (?, ?, ?, ?, ?, ?, ?)`, page.URL, page.FinalURL, page.Title, page.Text, string(links), page.Via, at)
		if err != nil {
			return err
		}
		pid, _ := res.LastInsertId()
		if _, err = tx.ExecContext(ctx, `INSERT INTO bb_pages_fts (rowid, title, text, url) VALUES (?, ?, ?, ?)`,
			pid, page.Title, page.Text, page.FinalURL); err != nil {
			return err
		}
	}
	if len(snapshot) > 0 {
		if _, err = tx.ExecContext(ctx, `INSERT INTO bb_status_snapshots (at, data) VALUES (?, ?)`, at, string(snapshot)); err != nil {
			return err
		}
	}
	return tx.Commit()
}

// openSession is the session id of the newest successful session create or
// release in the ledger when it was a create, else "".
func openSession(ctx context.Context, tx *sql.Tx) (string, error) {
	var id, summary string
	err := tx.QueryRowContext(ctx, `SELECT session_id, summary FROM bb_calls
		WHERE tool = 'session' AND ok = 1 AND (summary LIKE 'create%' OR summary LIKE 'release%')
		ORDER BY id DESC LIMIT 1`).Scan(&id, &summary)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	if err != nil || !strings.HasPrefix(summary, "create") {
		return "", err
	}
	return id, nil
}

// OpenLedgerReader opens a ledger read-only. It is not opened immutable:
// another process may be writing the ledger at the same time. found is false
// when the file does not exist or holds no ledger tables.
func OpenLedgerReader(ctx context.Context, path string) (*Store, bool, error) {
	if _, err := os.Stat(path); os.IsNotExist(err) {
		return nil, false, nil
	}
	dsn := "file:" + path + "?mode=ro&_pragma=busy_timeout(5000)&_pragma=mmap_size(0)"
	if err := ensureSQLiteDriverInitialized(ctx, dsn); err != nil {
		return nil, false, err
	}
	db, err := sql.Open("sqlite", dsn)
	if err != nil {
		return nil, false, fmt.Errorf("opening ledger %s: %w", path, err)
	}
	var n int
	if err := db.QueryRowContext(ctx, `SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'bb_calls'`).Scan(&n); err != nil {
		_ = db.Close()
		return nil, false, fmt.Errorf("opening ledger %s: %w", path, err)
	}
	if n == 0 {
		_ = db.Close()
		return nil, false, nil
	}
	return &Store{db: db, path: path}, true, nil
}

// collectRows drains rows through scan, closing them on every path.
func collectRows[T any](rows *sql.Rows, scan func(*sql.Rows) (T, error)) ([]T, error) {
	defer rows.Close()
	out := make([]T, 0)
	for rows.Next() {
		v, err := scan(rows)
		if err != nil {
			return nil, err
		}
		out = append(out, v)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return out, rows.Close()
}

// CallFilter narrows history.
type CallFilter struct {
	Tool      string
	Status    string // ok | failed | or an exact status such as error, lane_busy, refused, done
	SessionID string
	Since     time.Time
	Limit     int
}

// Calls returns ledger rows, newest first.
func (s *Store) Calls(ctx context.Context, f CallFilter) ([]CallRow, error) {
	where := []string{"1=1"}
	args := []any{}
	if f.Tool != "" {
		where = append(where, "tool = ?")
		args = append(args, f.Tool)
	}
	switch strings.ToLower(f.Status) {
	case "":
	case "ok":
		where = append(where, "ok = 1")
	case "failed":
		where = append(where, "ok = 0")
	default:
		where = append(where, "status = ?")
		args = append(args, f.Status)
	}
	if f.SessionID != "" {
		where = append(where, "session_id = ?")
		args = append(args, f.SessionID)
	}
	if !f.Since.IsZero() {
		where = append(where, "at >= ?")
		args = append(args, f.Since.UTC().Format(ledger.TimeFormat))
	}
	limit := f.Limit
	if limit <= 0 {
		limit = 50
	}
	args = append(args, limit)
	// #nosec G202 -- only constant predicates are joined; every value is a bound argument
	rows, err := s.db.QueryContext(ctx, `SELECT id, at, tool, summary, args, http_status, ok, status, error,
		duration_ms, cost_usd, session_id, url FROM bb_calls WHERE `+strings.Join(where, " AND ")+
		` ORDER BY id DESC LIMIT ?`, args...)
	if err != nil {
		return nil, err
	}
	return collectRows(rows, func(rows *sql.Rows) (CallRow, error) {
		var r CallRow
		var ok int
		var argText string
		var cost sql.NullFloat64
		if err := rows.Scan(&r.ID, &r.At, &r.Tool, &r.Summary, &argText, &r.HTTPStatus, &ok, &r.Status, &r.Error,
			&r.DurationMS, &cost, &r.SessionID, &r.URL); err != nil {
			return r, fmt.Errorf("scan call: %w", err)
		}
		r.OK = ok == 1
		if cost.Valid {
			v := cost.Float64
			r.CostUSD = &v
		}
		if argText != "" && argText != "{}" {
			r.Args = json.RawMessage(argText)
		}
		return r, nil
	})
}

// LatestPage returns the newest cached page whose url or final_url matches,
// or nil when there is none.
func (s *Store) LatestPage(ctx context.Context, url string) (*PageRow, error) {
	variants := urlVariants(url)
	placeholders := strings.TrimSuffix(strings.Repeat("?,", len(variants)), ",")
	args := make([]any, 0, len(variants)*2)
	for _, v := range variants {
		args = append(args, v)
	}
	for _, v := range variants {
		args = append(args, v)
	}
	// #nosec G202 -- placeholders is only "?," repeated; the URLs are bound arguments
	row := s.db.QueryRowContext(ctx, `SELECT url, final_url, title, text, links, via, fetched_at FROM bb_pages
		WHERE url IN (`+placeholders+`) OR final_url IN (`+placeholders+`) ORDER BY id DESC LIMIT 1`, args...)
	var p PageRow
	var links string
	if err := row.Scan(&p.URL, &p.FinalURL, &p.Title, &p.Text, &links, &p.Via, &p.FetchedAt); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, err
	}
	_ = json.Unmarshal([]byte(links), &p.Links)
	return &p, nil
}

// Pages lists cached pages, newest first, one row per URL.
func (s *Store) Pages(ctx context.Context, limit int) ([]PageRow, error) {
	if limit <= 0 {
		limit = 50
	}
	rows, err := s.db.QueryContext(ctx, `SELECT p.url, p.final_url, p.title, p.via, p.fetched_at FROM bb_pages p
		JOIN (SELECT url, MAX(id) AS id FROM bb_pages GROUP BY url) latest ON latest.id = p.id
		ORDER BY p.id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	return collectRows(rows, func(rows *sql.Rows) (PageRow, error) {
		var p PageRow
		err := rows.Scan(&p.URL, &p.FinalURL, &p.Title, &p.Via, &p.FetchedAt)
		return p, err
	})
}

// SearchPages runs a full-text query over cached pages, one hit per URL.
func (s *Store) SearchPages(ctx context.Context, query string, limit int) ([]PageRow, error) {
	match := ftsQuery(query)
	if match == "" {
		return make([]PageRow, 0), nil
	}
	if limit <= 0 {
		limit = 10
	}
	rows, err := s.db.QueryContext(ctx, `SELECT p.url, p.final_url, p.title, p.via, p.fetched_at,
			snippet(bb_pages_fts, 1, '[', ']', '…', 16)
		FROM bb_pages_fts JOIN bb_pages p ON p.id = bb_pages_fts.rowid
		WHERE bb_pages_fts MATCH ? ORDER BY rank, p.id DESC LIMIT ?`, match, limit*4)
	if err != nil {
		return nil, fmt.Errorf("full-text query: %w", err)
	}
	out := make([]PageRow, 0)
	seen := map[string]int{}
	for rows.Next() {
		var p PageRow
		if err := rows.Scan(&p.URL, &p.FinalURL, &p.Title, &p.Via, &p.FetchedAt, &p.Snippet); err != nil {
			_ = rows.Close()
			return nil, err
		}
		if i, dup := seen[p.URL]; dup {
			// A plain fetch has no title; take it from a read of the same URL.
			if out[i].Title == "" && p.Title != "" {
				out[i].Title = p.Title
			}
			continue
		}
		if len(out) >= limit {
			continue
		}
		seen[p.URL] = len(out)
		out = append(out, p)
	}
	if err := rows.Err(); err != nil {
		_ = rows.Close()
		return nil, err
	}
	return out, rows.Close()
}

// LatestSnapshot returns the newest stored status, or nil.
func (s *Store) LatestSnapshot(ctx context.Context) (*Snapshot, error) {
	var snap Snapshot
	var data string
	err := s.db.QueryRowContext(ctx, `SELECT at, data FROM bb_status_snapshots ORDER BY id DESC LIMIT 1`).Scan(&snap.At, &data)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	snap.Data = json.RawMessage(data)
	return &snap, nil
}

// SetAlias creates or replaces a session alias.
func (s *Store) SetAlias(ctx context.Context, a Alias) error {
	s.lockForWrite()
	defer s.unlockAfterWrite()
	_, err := s.db.ExecContext(ctx, `INSERT INTO bb_aliases (name, session_id, note, updated_at) VALUES (?, ?, ?, ?)
		ON CONFLICT(name) DO UPDATE SET session_id = excluded.session_id, note = excluded.note, updated_at = excluded.updated_at`,
		a.Name, a.SessionID, a.Note, a.UpdatedAt)
	return err
}

// GetAlias returns the alias, or nil.
func (s *Store) GetAlias(ctx context.Context, name string) (*Alias, error) {
	var a Alias
	err := s.db.QueryRowContext(ctx, `SELECT name, session_id, note, updated_at FROM bb_aliases WHERE name = ?`, name).
		Scan(&a.Name, &a.SessionID, &a.Note, &a.UpdatedAt)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// Aliases lists every alias by name.
func (s *Store) Aliases(ctx context.Context) ([]Alias, error) {
	rows, err := s.db.QueryContext(ctx, `SELECT name, session_id, note, updated_at FROM bb_aliases ORDER BY name`)
	if err != nil {
		return nil, err
	}
	return collectRows(rows, func(rows *sql.Rows) (Alias, error) {
		var a Alias
		err := rows.Scan(&a.Name, &a.SessionID, &a.Note, &a.UpdatedAt)
		return a, err
	})
}

// DeleteAlias removes an alias and reports whether it existed.
func (s *Store) DeleteAlias(ctx context.Context, name string) (bool, error) {
	s.lockForWrite()
	defer s.unlockAfterWrite()
	res, err := s.db.ExecContext(ctx, `DELETE FROM bb_aliases WHERE name = ?`, name)
	if err != nil {
		return false, err
	}
	n, _ := res.RowsAffected()
	return n > 0, nil
}

// LastCreatedSession is the newest session id a successful session create returned.
func (s *Store) LastCreatedSession(ctx context.Context) (string, error) {
	var id string
	err := s.db.QueryRowContext(ctx, `SELECT session_id FROM bb_calls
		WHERE tool = 'session' AND ok = 1 AND session_id != '' AND summary LIKE 'create%' ORDER BY id DESC LIMIT 1`).Scan(&id)
	if errors.Is(err, sql.ErrNoRows) {
		return "", nil
	}
	return id, err
}

// urlVariants matches a URL with and without its trailing slash, which is
// how the browser commonly reports the same page back.
func urlVariants(u string) []string {
	u = strings.TrimSpace(u)
	trimmed := strings.TrimRight(u, "/")
	if trimmed == u {
		return []string{u, u + "/"}
	}
	return []string{u, trimmed}
}

// ftsQuery turns free text into an FTS5 query of quoted terms (all must
// match), so punctuation in a user's query cannot break MATCH syntax.
func ftsQuery(q string) string {
	terms := strings.Fields(q)
	quoted := make([]string, 0, len(terms))
	for _, t := range terms {
		t = strings.ReplaceAll(t, `"`, "")
		if t != "" {
			quoted = append(quoted, `"`+t+`"`)
		}
	}
	return strings.Join(quoted, " ")
}

func boolInt(b bool) int {
	if b {
		return 1
	}
	return 0
}
