Sets cf /raw_t,mk_hours,cream_hours,curds_hours,p_milk,p_kefir,p_cream,p_curds/,
    rf /objective_rub,modelstat,solvestat,max_violation,spread_relative,
        objective_spread_relative,q_spread_relative,raw_used_t,mk_used_hours,
        cream_used_hours,curds_used_hours,raw_violation_t,mk_violation_hours,
        cream_violation_hours,curds_violation_hours,bound_violation_t,objective_check_rub,pass/;

File f /'results/%resultprefix%_results.csv'/;
f.pw = 32767;
f.nz = 0;
put f 'scenario_id,';
loop(cf,put cf.tl:0 ',';);
loop(j,put 'q_' j.tl:0 ',';);
loop(rf,put rf.tl:0 ',';);
put 'status,shadow_raw_rub_per_t,';
loop(r,put 'shadow_' r.tl:0 '_rub_per_hour,';);
loop(j,put 'a0_' j.tl:0 ',';);
loop(j,put 'ep_' j.tl:0 ',';);
loop(j,put 'ea_' j.tl:0 ',';);
loop(j,put 'qmin_' j.tl:0 ',';);
loop((r,j),put 'speed_' r.tl:0 '_' j.tl:0 ',';);
loop(j,put 'effective_price_' j.tl:0 ',';);
loop(j,put 'effective_input_' j.tl:0 ',';);
loop(j,put 'bound_marginal_' j.tl:0 '_rub_per_t,';);
put 'q0_t' /;
loop(s,
    put s.tl:0 ',';
    loop(cf,put conditions(s,cf):0:12 ',';);
    loop(j,put bestQ(s,j):0:12 ',';);
    loop(rf,put result(s,rf):0:12 ',';);
    put 'LOCAL_OPTIMUM_FOUND,' bestShadow(s,'raw'):0:12 ',';
    loop(r,put bestShadow(s,r):0:12 ',';);
    loop(j,put a0(j):0:12 ',';);
    loop(j,put ep(j):0:12 ',';);
    loop(j,put ea(j):0:12 ',';);
    loop(j,put qmin(j):0:12 ',';);
    loop((r,j),put speed(r,j):0:12 ',';);
    loop(j,put basePrice(s,j):0:12 ',';);
    loop(j,put baseInput(s,j):0:12 ',';);
    loop(j,put bestBound(s,j):0:12 ',';);
    put q0:0:12 /;
);
putclose f;

File h /'results/%resultprefix%_starts.csv'/;
h.pw = 32767;
h.nz = 0;
put h 'scenario_id,start_id,';
loop(j,put 'initial_' j.tl:0 ',';);
loop(j,put 'q_' j.tl:0 ',';);
put 'objective_rub,modelstat,solvestat,max_violation,raw_violation_t,line_violation_hours,bound_violation_t,objective_check_rub,accepted,pass,status' /;
loop((s,st),
    put s.tl:0 ',' st.tl:0 ',';
    loop(j,put startQ(s,st,j):0:12 ',';);
    loop(j,put runQ(s,st,j):0:12 ',';);
    put run(s,st,'objective_rub'):0:12 ',' run(s,st,'modelstat'):0:0 ',' run(s,st,'solvestat'):0:0 ',';
    put run(s,st,'max_violation'):0:12 ',' run(s,st,'raw_violation_t'):0:12 ',';
    put run(s,st,'line_violation_hours'):0:12 ',' run(s,st,'bound_violation_t'):0:12 ',';
    put run(s,st,'objective_check_rub'):0:12 ',' run(s,st,'accepted'):0:0 ',' run(s,st,'pass'):0:0 ',LOCAL_OPTIMUM_FOUND' /;
);
putclose h;

