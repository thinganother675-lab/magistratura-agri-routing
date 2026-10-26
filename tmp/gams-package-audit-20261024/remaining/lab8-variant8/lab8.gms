$title Lab 8.1 variant 8: base case and three starts
$include model.inc

Set s /base/;
Table conditions(s,*)
          raw_t  mk_hours  cream_hours  curds_hours  p_milk  p_kefir  p_cream  p_curds
    base   1400        21           18           18   24000    27000   138000    78000;

$setglobal resultprefix base
$include run_cases.inc
$include export_results.inc
display result, bestQ, basePrice, baseInput, bestShadow;

