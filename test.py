import duw.db as D

with D.session_scope() as S:
    S.add(D.RegisterValue(register=1, value=2))
    S.add(D.RegisterValue(register=1, value=3))
    S.add(D.RegisterValue(register=1, value=4))
with D.session_scope() as S:
    S.add(D.RegisterValue(register=2, value=2))
    S.add(D.RegisterValue(register=2, value=3))
    S.add(D.RegisterValue(register=2, value=4))

with D.session_scope() as S:
    for rv in S.query(D.RegisterValue):
        print(rv.dt, rv.register, rv.value)
