// Package update handles atomic binary self-update.
package update

import (
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

const releaseAPIURL = "https://api.github.com/repos/skonlabs/bugpilot/releases/latest"

type Release struct {
	TagName string  `json:"tag_name"`
	Assets  []Asset `json:"assets"`
}

type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadURL string `json:"browser_download_url"`
}

// Download downloads the asset at latestURL, replaces the current executable
// atomically, and verifies the new binary runs before committing.
//
// Steps:
//  1. Download to a temp file in the same directory as the current binary
//  2. Verify: run `<tmpfile> version` — bail out if it fails
//  3. chmod 0755
//  4. os.Rename (atomic on same filesystem)
func Download(latestURL string, progressFn func(downloaded, total int64)) error {
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("find executable: %w", err)
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return fmt.Errorf("resolve symlinks: %w", err)
	}

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(latestURL)
	if err != nil {
		return fmt.Errorf("download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("download status %d", resp.StatusCode)
	}

	total, _ := strconv.ParseInt(resp.Header.Get("Content-Length"), 10, 64)

	tmpF, err := os.CreateTemp(filepath.Dir(exe), "bugpilot-*.tmp")
	if err != nil {
		if errors.Is(err, os.ErrPermission) {
			return fmt.Errorf(
				"permission denied writing to %s — try: sudo bugpilot update",
				filepath.Dir(exe),
			)
		}
		return fmt.Errorf("create temp file: %w", err)
	}
	tmpFile := tmpF.Name()

	// Download with progress
	var downloaded int64
	buf := make([]byte, 32*1024)
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, writeErr := tmpF.Write(buf[:n]); writeErr != nil {
				tmpF.Close()
				os.Remove(tmpFile)
				return fmt.Errorf("write temp file: %w", writeErr)
			}
			downloaded += int64(n)
			if progressFn != nil {
				progressFn(downloaded, total)
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			tmpF.Close()
			os.Remove(tmpFile)
			return fmt.Errorf("read download: %w", readErr)
		}
	}
	tmpF.Close()

	// Verify the downloaded binary runs before we swap it in
	if err := os.Chmod(tmpFile, 0755); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("set permissions: %w", err)
	}
	if out, err := exec.Command(tmpFile, "version").CombinedOutput(); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("binary verification failed (%v): %s", err, strings.TrimSpace(string(out)))
	}

	// Atomic replace
	if err := os.Rename(tmpFile, exe); err != nil {
		os.Remove(tmpFile)
		if errors.Is(err, os.ErrPermission) {
			return fmt.Errorf(
				"permission denied replacing %s — try: sudo bugpilot update",
				exe,
			)
		}
		return fmt.Errorf("replace binary: %w", err)
	}

	return nil
}

// AssetURLForPlatform returns the download URL for the current OS/arch.
// Asset names follow the convention used by install.sh:
//
//	bugpilot-linux-x86_64
//	bugpilot-linux-arm64
//	bugpilot-darwin-x86_64
//	bugpilot-darwin-arm64
//	bugpilot-windows-x86_64.exe
func AssetURLForPlatform(assets []Asset) (string, error) {
	goos := runtime.GOOS
	goarch := runtime.GOARCH

	// Map Go arch names to the names used in release asset filenames
	archMap := map[string]string{
		"amd64": "x86_64",
		"arm64": "arm64",
	}
	archName, ok := archMap[goarch]
	if !ok {
		return "", fmt.Errorf("unsupported architecture: %s", goarch)
	}

	// OS names match uname -s output (lowercase), same as install.sh
	osMap := map[string]string{
		"linux":   "linux",
		"darwin":  "darwin",
		"windows": "windows",
	}
	osName, ok := osMap[goos]
	if !ok {
		return "", fmt.Errorf("unsupported OS: %s", goos)
	}

	for _, asset := range assets {
		name := strings.ToLower(asset.Name)
		if strings.Contains(name, osName) && strings.Contains(name, archName) {
			if goos == "windows" && !strings.HasSuffix(name, ".exe") {
				continue
			}
			return asset.BrowserDownloadURL, nil
		}
	}
	return "", fmt.Errorf("no release asset found for %s/%s — check https://github.com/skonlabs/bugpilot/releases", goos, goarch)
}
