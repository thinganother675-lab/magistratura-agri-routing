Sets st /start1*start3/, pass /normal, strict/;
Table initial(st,j)
             milk   kefir  cream  curds
    start1     25      30    1.5   1.25
    start2    300     500     30      5
    start3    800     100     45     35;

Parameters result(s,*), bestQ(s,j), run(s,st,*), runQ(s,st,j),
    startQ(s,st,j), startUpper(j), used(r), bestShadow(s,*), bestBound(s,j), basePrice(s,j), baseInput(s,j);
Scalars best, spread, objSpread, qSpread, violation, rawUsed, boundViolation,
    rawViolation, lineViolation, objectiveCheck, accepted;

loop(s,
    rawCapacity = conditions(s,'raw_t');
    hours('mainline') = conditions(s,'mk_hours');
    hours('creamline') = conditions(s,'cream_hours');
    hours('curdsline') = conditions(s,'curds_hours');
    price('milk') = conditions(s,'p_milk');
    price('kefir') = conditions(s,'p_kefir');
    price('cream') = conditions(s,'p_cream');
    price('curds') = conditions(s,'p_curds');
    startUpper(j) = smin(r$speed(r,j),speed(r,j)*hours(r));
    abort$(smin(j,startUpper(j)-qmin(j))<0) 'Lower bound exceeds line capacity',s;
    spread = 0;
    loop(pass$(ord(pass)=1 or spread>.001),
        dairy.optfile = ord(pass);
        best = -inf;
        loop(st,
            q.l(j) = min(startUpper(j),max(qmin(j),initial(st,j)));
            startQ(s,st,j) = q.l(j);
            q.m(j) = 0;
            revenue.l = sum(j,price(j)*q0*rPower(q.l(j)/q0,1+ep(j)))/1e6;
            revenue.m = 0; raw.m = 0; line.m(r) = 0; objective.m = 0;
            solve dairy using nlp maximizing revenue;
            rawUsed = sum(j,a0(j)*q0*rPower(q.l(j)/q0,1+ea(j)));
            used(r) = sum(j,time(r,j)*q.l(j));
            rawViolation = max(0,rawUsed-rawCapacity);
            lineViolation = smax(r,max(0,used(r)-hours(r)));
            boundViolation = smax(j,max(0,qmin(j)-q.l(j),q.l(j)-q.up(j)));
            violation = max(rawViolation,lineViolation,boundViolation);
            objectiveCheck = abs(revenue.l*1e6-sum(j,price(j)*q0*rPower(q.l(j)/q0,1+ep(j))));
            accepted = ((dairy.modelstat=1 or dairy.modelstat=2) and dairy.solvestat=1 and violation<1e-5 and objectiveCheck<.01);
            run(s,st,'objective_rub') = revenue.l*1e6;
            run(s,st,'modelstat') = dairy.modelstat;
            run(s,st,'solvestat') = dairy.solvestat;
            run(s,st,'max_violation') = violation;
            run(s,st,'raw_violation_t') = rawViolation;
            run(s,st,'line_violation_hours') = lineViolation;
            run(s,st,'bound_violation_t') = boundViolation;
            run(s,st,'objective_check_rub') = objectiveCheck;
            run(s,st,'accepted') = accepted;
            run(s,st,'pass') = ord(pass);
            runQ(s,st,j) = q.l(j);
            if(accepted and revenue.l>best,
                best = revenue.l;
                bestQ(s,j) = q.l(j);
                result(s,'objective_rub') = revenue.l*1e6;
                result(s,'modelstat') = dairy.modelstat;
                result(s,'solvestat') = dairy.solvestat;
                result(s,'max_violation') = violation;
                result(s,'raw_used_t') = rawUsed;
                result(s,'mk_used_hours') = used('mainline');
                result(s,'cream_used_hours') = used('creamline');
                result(s,'curds_used_hours') = used('curdsline');
                result(s,'raw_violation_t') = rawViolation;
                result(s,'mk_violation_hours') = max(0,used('mainline')-hours('mainline'));
                result(s,'cream_violation_hours') = max(0,used('creamline')-hours('creamline'));
                result(s,'curds_violation_hours') = max(0,used('curdsline')-hours('curdsline'));
                result(s,'bound_violation_t') = boundViolation;
                result(s,'objective_check_rub') = objectiveCheck;
                bestShadow(s,'raw') = raw.m*1e6;
                loop(r,bestShadow(s,r) = line.m(r)*1e6;);
                bestBound(s,j) = q.m(j)*1e6;
                basePrice(s,j) = price(j)*rPower(q.l(j)/q0,ep(j));
                baseInput(s,j) = a0(j)*rPower(q.l(j)/q0,ea(j));
            );
        );
        abort$(smin(st,run(s,st,'accepted'))=0) 'At least one start failed. Inspect listing.',s,run;
        objSpread = (smax(st,run(s,st,'objective_rub'))-smin(st,run(s,st,'objective_rub')))/max(1,abs(result(s,'objective_rub')));
        qSpread = smax(j,(smax(st,runQ(s,st,j))-smin(st,runQ(s,st,j)))/max(1,abs(bestQ(s,j))));
        spread = max(objSpread,qSpread);
        result(s,'pass') = ord(pass);
    );
    result(s,'spread_relative') = spread;
    result(s,'objective_spread_relative') = objSpread;
    result(s,'q_spread_relative') = qSpread;
    abort$(spread>.001) 'Starts still differ by more than 0.1 percent after stricter retry',s,spread;
);

