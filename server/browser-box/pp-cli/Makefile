.PHONY: build test lint install clean

BIN_EXT := $(if $(filter windows,$(shell go env GOOS)),.exe,)

build:
	go build -trimpath -o bin/browser-box-pp-cli$(BIN_EXT) ./cmd/browser-box-pp-cli

test:
	go test ./...

lint:
	golangci-lint run

install:
	go install ./cmd/browser-box-pp-cli

clean:
	rm -rf bin/

build-mcp:
	go build -trimpath -o bin/browser-box-pp-mcp$(BIN_EXT) ./cmd/browser-box-pp-mcp

install-mcp:
	go install ./cmd/browser-box-pp-mcp

build-all: build build-mcp
