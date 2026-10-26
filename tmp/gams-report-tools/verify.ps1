$ErrorActionPreference = 'Stop'
$g = Import-Csv (Join-Path $PSScriptRoot '../../coursework/gams-2026/lab2-variant8/gams_result.csv')
$m=[double]$g.milk
$k=[double]$g.kefir
$c=[double]$g.cream
$s=[double]$g.skim
$raw=1.01*$m+1.01*$k+9.45*$c+0.31*$s
$line=$m/5+$k/6+$s/6
$creamHours=$c/0.3
$revenue=2.4*$m+2.7*$k+13.8*$c+0.79*$s
$upper=(92.0/63)*140+(17561.0/3150)*21
$tol=1e-8
# Verify each coefficient of the independent upper-bound identity.
$identityError=@(
    (92.0/63)*1.01+(17561.0/3150)/5-(997.0/5250)-2.4
    (92.0/63)*1.01+(17561.0/3150)/6+(5593.0/18900)-2.7
    (92.0/63)*9.45-13.8
    (92.0/63)*0.31+(17561.0/3150)/6-2*(5593.0/18900)-0.79
)
foreach($value in $identityError) {if([math]::Abs($value) -gt $tol) {throw 'Upper bound identity failed'}}
if($m -lt -$tol -or $k -lt -$tol -or $c -lt -$tol -or $s -lt -$tol) {throw 'Negative output'}
if($raw -gt 140+$tol -or $line -gt 21+$tol -or $creamHours -gt 16+$tol -or $k-2*$s -gt $tol) {throw 'Constraint violation'}
if([math]::Abs($revenue-$upper) -gt $tol -or [math]::Abs($revenue-[double]$g.revenue_thousand_rub) -gt $tol) {throw 'Objective or bound mismatch'}
if($g.modelstat -ne '1' -or $g.solvestat -ne '1') {throw 'Unexpected GAMS status'}
[pscustomobject]@{
    raw_centners=$raw
    main_hours=$line
    cream_hours=$creamHours
    skim_share=$s/($k+$s)
    revenue_thousand_rub=$revenue
    upper_bound_thousand_rub=$upper
    dual_gap=$upper-$revenue
    gams_modelstat=$g.modelstat
    gams_solvestat=$g.solvestat
    passed=$true
} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $PSScriptRoot '../../coursework/gams-2026/lab2-variant8/verification.json')

