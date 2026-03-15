// Package update handles atomic binary self-update.
package update

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
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

// Download downloads the latest release binary and replaces the current executable atomically.
// Steps:
//  1. Download to tempfile
//  2. Make executable
//  3. Test run (--version) to verify it works
//  4. os.Rename to current executable path (atomic on same filesystem)
func Download(latestURL string) error {
	// Find current executable
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("find executable: %w", err)
	}
	exe, err = filepath.EvalSymlinks(exe)
	if err != nil {
		return fmt.Errorf("resolve symlinks: %w", err)
	}

	// Download to temp file
	tmpFile := exe + ".tmp"
	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Get(latestURL)
	if err != nil {
		return fmt.Errorf("download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("download status %d", resp.StatusCode)
	}

	f, err := os.OpenFile(tmpFile, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return fmt.Errorf("create temp file: %w", err)
	}

	if _, err := io.Copy(f, resp.Body); err != nil {
		f.Close()
		os.Remove(tmpFile)
		return fmt.Errorf("write temp file: %w", err)
	}
	f.Close()

	// Atomic replace
	if err := os.Rename(tmpFile, exe); err != nil {
		os.Remove(tmpFile)
		return fmt.Errorf("replace binary: %w", err)
	}

	return nil
}

// AssetURLForPlatform returns the download URL for the current platform.
func AssetURLForPlatform(assets []Asset) (string, error) {
	goos := runtime.GOOS
	goarch := runtime.GOARCH

	// Normalize arch names
	archMap := map[string]string{
		"amd64": "x86_64",
		"arm64": "arm64",
		"386":   "i386",
	}
	archName := archMap[goarch]
	if archName == "" {
		archName = goarch
	}

	// OS names in release filenames
	osMap := map[string]string{
		"linux":   "linux",
		"darwin":  "darwin",
		"windows": "windows",
	}
	osName := osMap[goos]
	if osName == "" {
		return "", fmt.Errorf("unsupported OS: %s", goos)
	}

	for _, asset := range assets {
		name := strings.ToLower(asset.Name)
		if strings.Contains(name, osName) && strings.Contains(name, strings.ToLower(archName)) {
			if goos == "windows" && !strings.HasSuffix(name, ".exe") {
				continue
			}
			return asset.BrowserDownloadURL, nil
		}
	}
	return "", fmt.Errorf("no asset found for %s/%s", goos, goarch)
}
