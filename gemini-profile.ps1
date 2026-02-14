param(
  [ValidateSet('default','dev','browser','research','ops','fidelity','full','screen-readonly','screen-operator','sidecar-operator')]
  [string]$Profile = 'full'
)

$profilesDir = Join-Path $PSScriptRoot "profiles"
$src = Join-Path $profilesDir ("config.$Profile.toml")
if (!(Test-Path $src)) {
  Write-Error "Profile not found: $Profile"
  exit 1
}
Copy-Item -Force $src Join-Path $PSScriptRoot "config.toml"
Write-Output "Active Gemini profile: $Profile"
