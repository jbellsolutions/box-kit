// Copyright 2026 jbellsolutions and contributors. Licensed under Apache-2.0. See LICENSE.

package store

import (
	"context"
	"database/sql"
	"fmt"
)

// migrateExtras runs after the generated store migrations and before the
// schema-version stamp. It is the canonical place for novel-feature auxiliary
// tables that need to live in the local store.
//
// Edit this file when adding tables for novel commands. Keep migrations
// idempotent with CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS so
// every store open can safely re-run them.
func (s *Store) migrateExtras(ctx context.Context, conn *sql.Conn) error {
	migrations := []string{
		// browser-box: the local memory the box itself does not keep.
		`CREATE TABLE IF NOT EXISTS bb_calls (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			at TEXT NOT NULL,
			tool TEXT NOT NULL,
			summary TEXT NOT NULL DEFAULT '',
			args TEXT NOT NULL DEFAULT '{}',
			http_status INTEGER NOT NULL DEFAULT 0,
			ok INTEGER NOT NULL DEFAULT 0,
			status TEXT NOT NULL DEFAULT '',
			error TEXT NOT NULL DEFAULT '',
			duration_ms INTEGER NOT NULL DEFAULT 0,
			cost_usd REAL,
			session_id TEXT NOT NULL DEFAULT '',
			url TEXT NOT NULL DEFAULT ''
		)`,
		`CREATE INDEX IF NOT EXISTS idx_bb_calls_at ON bb_calls(at)`,
		`CREATE INDEX IF NOT EXISTS idx_bb_calls_tool ON bb_calls(tool, at)`,
		`CREATE TABLE IF NOT EXISTS bb_pages (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			url TEXT NOT NULL,
			final_url TEXT NOT NULL DEFAULT '',
			title TEXT NOT NULL DEFAULT '',
			text TEXT NOT NULL DEFAULT '',
			links TEXT NOT NULL DEFAULT '[]',
			via TEXT NOT NULL DEFAULT '',
			fetched_at TEXT NOT NULL
		)`,
		`CREATE INDEX IF NOT EXISTS idx_bb_pages_url ON bb_pages(url, fetched_at)`,
		`CREATE INDEX IF NOT EXISTS idx_bb_pages_final_url ON bb_pages(final_url, fetched_at)`,
		`CREATE VIRTUAL TABLE IF NOT EXISTS bb_pages_fts USING fts5(title, text, url)`,
		`CREATE TABLE IF NOT EXISTS bb_status_snapshots (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			at TEXT NOT NULL,
			data TEXT NOT NULL
		)`,
		`CREATE TABLE IF NOT EXISTS bb_aliases (
			name TEXT PRIMARY KEY,
			session_id TEXT NOT NULL,
			note TEXT NOT NULL DEFAULT '',
			updated_at TEXT NOT NULL
		)`,
	}
	for _, m := range migrations {
		if _, err := conn.ExecContext(ctx, m); err != nil {
			return fmt.Errorf("extra migration failed: %w", err)
		}
	}
	return nil
}
