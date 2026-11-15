# centre strip: both 9 V gate-drive LDOs (PACK_P is right underneath on B.Cu)
A=lambda *a,**k: auto(P,*a,**k)
for U,Q,C8,C7,Ra,Rb,Rc,D,x,qy,qrot in (('U406','Q409','C458','C457','R452','R453','R454','D411',102.35,99.9,0),
                                      ('U506','Q509','C558','C557','R552','R553','R554','D511',98.35,96.35,180)):
    put(U,x,105.0,90)
    put(Q,100.27,qy,qrot)
    put(C8,x,109.25,0)
    put(Ra,x-1.0,110.85,0); put(Rb,x+0.95,110.85,0)
    put(D,x-0.2,112.2,180)
    put(C7,x-0.2,113.8,0)
    if Rc=='R454': A(Rc,pins={'1':Q+'.3'},at=(x,101.2))
