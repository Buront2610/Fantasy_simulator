param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Profile,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

python scripts/quality_gate.py $Profile @RemainingArgs
exit $LASTEXITCODE
