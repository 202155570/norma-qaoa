"""padopauli on XY-mixer QAOA: accuracy of <Z_u> vs an exact state vector (N=10, k=3) and compile+run time of the
complete-graph mixer at p=2, w=4 for N=12,16,20. Start |1^k 0^(n-k)> (padopauli starts from |0...0>, so no Dicke
state); mixer = one rxx+ryy pass over the ring or over all pairs. argv: acc | time   (hard.md result 13)
"""
import numpy as np, torch, time, sys
from padopauli import Circuit
from scipy.sparse.linalg import expm_multiply
import scipy.sparse as sp
g1,b1,g2,b2=0.37,0.21,0.25,0.15
def inst(n,k,seed=0):
    rng=np.random.default_rng(seed); h=rng.normal(size=n); J=[(i,j,rng.normal()*0.5) for i in range(n) for j in range(i+1,n)]; return h,J
def build(n,k,h,J,pairs,layers):
    qc=Circuit(n_qubits=n); meta=[]
    for i in range(k): qc.x(i)
    for g,b in layers:
        for i in range(n): qc.rz(i,param_idx=len(meta)); meta.append(2*g*h[i])
        for i,j,v in J: qc.rzz(i,j,param_idx=len(meta)); meta.append(2*g*v)
        for i,j in pairs:
            qc.rxx(i,j,param_idx=len(meta)); meta.append(b)
            qc.ryy(i,j,param_idx=len(meta)); meta.append(b)
    return qc, torch.tensor(meta,dtype=torch.float64)
def exact(n,k,h,J,pairs,layers):
    N=2**n; idx=np.arange(N); bits=lambda q:(idx>>(n-1-q))&1; z=[1-2*bits(q) for q in range(n)]
    psi=np.zeros(N,complex); psi[sum(1<<(n-1-i) for i in range(k))]=1
    for g,b in layers:
        d=sum(g*h[i]*z[i] for i in range(n))+sum(g*v*z[i]*z[j] for i,j,v in J); psi=np.exp(-1j*d)*psi
        for i,j in pairs:
            # XX and YY on (i,j): XX flips both; YY flips both with sign -z_i z_j
            flip=idx^(1<<(n-1-i))^(1<<(n-1-j))
            for sgn in (1,-1):
                A=sp.csr_matrix(((np.ones(N) if sgn==1 else -(z[i]*z[j]).astype(float)),(flip,idx)),shape=(N,N))
                psi=expm_multiply(-1j*b/2*A,psi)
    return np.array([np.real(np.vdot(psi,z[u]*psi)) for u in range(n)])
mode=sys.argv[1]
if mode=="acc":
    n,k=10,3; h,J=inst(n,k)
    for name,pairs in (("ring",[(i,(i+1)%n) for i in range(n)]),("full",[(i,j) for i in range(n) for j in range(i+1,n)])):
        for L in ([(g1,b1)],[(g1,b1),(g2,b2)]):
            ex=exact(n,k,h,J,pairs,L)
            for w in (2,4,6):
                qc,th=build(n,k,h,J,pairs,L); t=time.time()
                qc.compile(observables=[[("Z",[u],1.0)] for u in range(n)],preset="cpu",dtype="float64",max_weight=w,verbosity=0)
                v=qc.expvals(th).detach().numpy()
                print(name,"p",len(L),"w",w,"max|err| %.2e"%np.abs(v-ex).max(),"%.1fs"%(time.time()-t),flush=True)
else:
    for n in (12,16,20):
        k=n//4; h,J=inst(n,k)
        for w in (4,):
            qc,th=build(n,k,h,J,[(i,j) for i in range(n) for j in range(i+1,n)],[(g1,b1),(g2,b2)]); t=time.time()
            qc.compile(observables=[[("Z",[0],1.0)]],preset="cpu",dtype="float64",max_weight=w,verbosity=0)
            v=qc.expvals(th); print("full p2 n",n,"w",w,"Z0 %.4f"%float(v[0]),"%.1fs"%(time.time()-t),flush=True)
