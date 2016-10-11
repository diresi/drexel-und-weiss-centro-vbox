import duw.db as D

with D.scoped_session() as S:
    S.add(D.RegisterValue(dev=9030, reg=1, val=2))
    S.add(D.RegisterValue(dev=9030, reg=1, val=3))
    S.add(D.RegisterValue(dev=9030, reg=1, val=4))
with D.scoped_session() as S:
    S.add(D.RegisterValue(dev=9050, reg=2, val=2))
    S.add(D.RegisterValue(dev=9050, reg=2, val=3))
    S.add(D.RegisterValue(dev=9050, reg=2, val=4))

with D.scoped_session() as S:
    for rv in S.query(D.RegisterValue):
        print(rv.dt, rv.dev, rv.reg, rv.val)
for rv in D.RegisterValue.query.all():
    print(rv.dt, rv.dev, rv.reg, rv.val)
