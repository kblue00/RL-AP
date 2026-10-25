param(
    [string]$HidMaestroSource = (Join-Path $PSScriptRoot '..\HIDMaestro')
)
$project = Join-Path $PSScriptRoot 'RocketLeagueInputBridge.csproj'
if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    throw 'The .NET 10 SDK is required to build and run the input bridge.'
}
$hmProject = Join-Path $HidMaestroSource 'sdk\HIDMaestro.Core\HIDMaestro.Core.csproj'
if (-not (Test-Path -LiteralPath $hmProject)) {
    throw "HIDMaestro source was not found at '$HidMaestroSource'. Pass its checkout path to this script."
}
dotnet run --project $project -p:HMSourceRoot="$HidMaestroSource"
exit $LASTEXITCODE
