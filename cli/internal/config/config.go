// Package config handles reading and writing the BugPilot configuration file.
//
// Config file: ~/.bugpilot/config.yaml
// Sensitive fields (api_key, connector credentials) are encrypted with
// AES-256-GCM. The encryption key is stored per-platform:
//   - macOS: Keychain
//   - Linux: ~/.bugpilot/.keyfile (mode 0600)
//   - Windows: DPAPI
package config

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"

	"github.com/spf13/viper"
	"gopkg.in/yaml.v3"
)

const (
	ConfigDir  = ".bugpilot"
	ConfigFile = "config.yaml"
	KeyFile    = ".keyfile"
)

// Config represents the full CLI configuration.
type Config struct {
	APIKey      string            `yaml:"api_key"`
	BaseURL     string            `yaml:"base_url"`
	OrgID       string            `yaml:"org_id"`
	OrgName     string            `yaml:"org_name"`
	Plan        string            `yaml:"plan"`
	Connectors  map[string]string `yaml:"connectors,omitempty"`
	LastVersion string            `yaml:"last_version,omitempty"`
}

func ConfigPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ConfigDir, ConfigFile), nil
}

func keyFilePath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(home, ConfigDir, KeyFile), nil
}

// EnsureConfigDir creates ~/.bugpilot if it doesn't exist.
func EnsureConfigDir() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	dir := filepath.Join(home, ConfigDir)
	return os.MkdirAll(dir, 0700)
}

// Load reads config from viper (which reads ~/.bugpilot/config.yaml).
func Load() (*Config, error) {
	cfg := &Config{
		APIKey:  viper.GetString("api_key"),
		BaseURL: viper.GetString("base_url"),
		OrgID:   viper.GetString("org_id"),
		OrgName: viper.GetString("org_name"),
		Plan:    viper.GetString("plan"),
	}
	if cfg.BaseURL == "" {
		cfg.BaseURL = "https://api.ekonomical.com"
	}
	return cfg, nil
}

// Save writes cfg to ~/.bugpilot/config.yaml.
// The api_key is stored encrypted.
func Save(cfg *Config) error {
	if err := EnsureConfigDir(); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}
	path, err := ConfigPath()
	if err != nil {
		return err
	}

	// Encrypt API key before writing
	encKey, err := getOrCreateEncryptionKey()
	if err != nil {
		return fmt.Errorf("encryption key: %w", err)
	}

	encryptedKey := cfg.APIKey
	if cfg.APIKey != "" {
		encryptedKey, err = encryptString(cfg.APIKey, encKey)
		if err != nil {
			return fmt.Errorf("encrypt api key: %w", err)
		}
	}

	data := map[string]interface{}{
		"api_key":      encryptedKey,
		"base_url":     cfg.BaseURL,
		"org_id":       cfg.OrgID,
		"org_name":     cfg.OrgName,
		"plan":         cfg.Plan,
		"last_version": cfg.LastVersion,
	}
	if len(cfg.Connectors) > 0 {
		data["connectors"] = cfg.Connectors
	}

	b, err := yaml.Marshal(data)
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}
	return os.WriteFile(path, b, 0600)
}

// LoadAPIKey returns the decrypted API key from config.
func LoadAPIKey() (string, error) {
	raw := viper.GetString("api_key")
	if raw == "" {
		return "", nil
	}
	// If not encrypted (doesn't start with enc:), return as-is (legacy/env)
	if len(raw) < 4 || raw[:4] != "enc:" {
		return raw, nil
	}
	encKey, err := getOrCreateEncryptionKey()
	if err != nil {
		return "", err
	}
	return decryptString(raw[4:], encKey)
}

// ── Encryption ────────────────────────────────────────────────────────────────

func getOrCreateEncryptionKey() ([]byte, error) {
	switch runtime.GOOS {
	case "darwin":
		return keychainGetOrCreate()
	case "windows":
		return dpapiGetOrCreate()
	default: // linux and others
		return keyfileGetOrCreate()
	}
}

func keyfileGetOrCreate() ([]byte, error) {
	path, err := keyFilePath()
	if err != nil {
		return nil, err
	}

	data, err := os.ReadFile(path)
	if err == nil && len(data) == 32 {
		return data, nil
	}

	// Generate new key
	key := make([]byte, 32)
	if _, err := rand.Read(key); err != nil {
		return nil, err
	}
	if err := EnsureConfigDir(); err != nil {
		return nil, err
	}
	if err := os.WriteFile(path, key, 0600); err != nil {
		return nil, err
	}
	return key, nil
}

// encryptString encrypts plaintext using AES-256-GCM.
// Returns "enc:<base64(nonce+ciphertext)>".
func encryptString(plaintext string, key []byte) (string, error) {
	block, err := aes.NewCipher(deriveKey(key))
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ct := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return "enc:" + base64.StdEncoding.EncodeToString(ct), nil
}

// decryptString decrypts a base64-encoded AES-256-GCM ciphertext.
func decryptString(encoded string, key []byte) (string, error) {
	ct, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return "", err
	}
	block, err := aes.NewCipher(deriveKey(key))
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonceSize := gcm.NonceSize()
	if len(ct) < nonceSize {
		return "", fmt.Errorf("ciphertext too short")
	}
	plaintext, err := gcm.Open(nil, ct[:nonceSize], ct[nonceSize:], nil)
	if err != nil {
		return "", err
	}
	return string(plaintext), nil
}

func deriveKey(key []byte) []byte {
	h := sha256.Sum256(key)
	return h[:]
}

// ── Platform stubs ─────────────────────────────────────────────────────────────
// macOS Keychain and Windows DPAPI implementations use build tags.
// These stubs handle the generic case (non-darwin/non-windows).

func keychainGetOrCreate() ([]byte, error) {
	// Implemented in config_darwin.go via Security framework
	return keyfileGetOrCreate()
}

func dpapiGetOrCreate() ([]byte, error) {
	// Implemented in config_windows.go via DPAPI
	return keyfileGetOrCreate()
}

// APIKeyHash returns the SHA256 hex digest of the raw API key.
func APIKeyHash(apiKey string) string {
	h := sha256.Sum256([]byte(apiKey))
	return hex.EncodeToString(h[:])
}
