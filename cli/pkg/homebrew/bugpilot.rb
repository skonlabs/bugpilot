# Homebrew formula for the BugPilot CLI.
#
# This file lives in a Homebrew tap repo (e.g. skonlabs/homebrew-tap).
# Users install with:
#   brew tap skonlabs/tap
#   brew install bugpilot
#
# To update after a release:
#   1. Download the new macOS binaries from the GitHub Release.
#   2. Compute sha256: shasum -a 256 bugpilot-macos-*
#   3. Update the `url` and `sha256` fields below for each bottle block.
#   4. Bump `version`.
#   5. Commit and push to the tap repo.

class Bugpilot < Formula
  desc     "CLI-first developer tool for debugging production incidents"
  homepage "https://bugpilot.io"
  version  "0.4.0"
  license  "Proprietary"

  on_arm do
    url "https://github.com/skonlabs/bugpilot/releases/download/v#{version}/bugpilot-macos-arm64"
    sha256 "f244590aa3538479a47ef9a4a2ca44e1f87e7d92cfcb7cc82370318decf3fab8"
  end

  on_intel do
    url "https://github.com/skonlabs/bugpilot/releases/download/v#{version}/bugpilot-macos-amd64"
    sha256 "0e7fec1d889c7ff3cfc554b993c6fdf4bbe404980fa274d5cae10b702929d30b"
  end

  def install
    if Hardware::CPU.arm?
      bin.install "bugpilot-macos-arm64" => "bugpilot"
    else
      bin.install "bugpilot-macos-amd64" => "bugpilot"
    end
  end

  # Shell completion (generated from the CLI at install time).
  def caveats
    <<~EOS
      Shell completions are not installed automatically.
      To enable them, add one of the following to your shell profile:

        # bash (~/.bash_profile or ~/.bashrc)
        eval "$(bugpilot --completion bash)"

        # zsh (~/.zshrc)
        eval "$(bugpilot --completion zsh)"

        # fish (~/.config/fish/config.fish)
        bugpilot --completion fish | source
    EOS
  end

  test do
    system "#{bin}/bugpilot", "--version"
  end
end
