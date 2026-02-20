function gemini {
    python "$PSScriptRoot\scripts\sovereign.py" @args
}
Export-ModuleMember -Function gemini
