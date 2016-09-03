#!/usr/bin/env python

import sys
import numpy as np
import matplotlib.pyplot as plt
import collections

eV = 27.2113966413442 # Hartrees

def V(r, Z):
    pot = np.zeros(len(r))
    for i in range(0, len(r)):
        if r[i] != 0:
            pot[i] = -Z/r[i]
	else:
	    pot[i] = pot[i-1]
    return pot

def init(dx, N, xmin):
    r = np.zeros(N, dtype=np.float64)
    for i in range(0, N):
        r[i] = np.exp(xmin + i*dx)
    return r

# for each point x_i, we get psi_i
# for which the eq. is:
# (12 - 10 f_n) y_n - f_{n-1} y_{n-1} - f_{n+1} y_{n+1} + (s[i+1] + 10.0*s[i] + s[i-1]) = 0
# y is the rescaled wave function
# y = 1/(sqrt(r)) * xi
# xi = r*R(r), where R(r) is the radial solution
# the xi -> y transformation prevents a first derivative from appearing in the Schroedinger eq.
# a and f re the temporary variables in the Numerov method
# we want to solve deriv(deriv(y)) + [2m_e/hbar^2 r^2 (E - V)  - (l+0.5)^2 ] y = 0
# using Numerov's method:
# a = 2 m / hbar^2 * r^2 * (E - V)  - (l+0.5)^2
# f = 1 + a * dx^2/12
# y_{n+1} = ((12 - 10 f_n) y_n - f_{n-1} y_{n-1}) / f_{n+1}

def nodes(n, l):
    return n - l - 1


## potential calculation
def getPotentialH(r, phiList):
    totalVd = np.zeros(len(r), dtype=np.float64)
    for iOrb in phiList.keys():
	# So, in summary:
	# 0) calculate rho(r) = W(r)^2
	# 1) calculate Q(r) = 4*pi*sum_r'=0^r rho(r)*r^2*dr
	# 2) calculate E(r) = Q(r)/(4*pi*r^2)
	# 3) calculate Vd(r) = sum_r'=inf^r E(r)*dr
        E = np.zeros(len(r), dtype=np.float64)
        rho = np.zeros(len(r), dtype=np.float64)
        for z in range(0, len(r)):
            rho[z] = phiList[iOrb].rpsi[z]**2
        Q = 0
        for z in range(0, len(r)):
            dr = 0
            if z >= 1:
                dr = r[z] - r[z-1]
            else:
                dr = r[z]
            Q += 4*np.pi*rho[z]*r[z]**2*dr
            # this is E:
            E[z] = Q/(4*np.pi*r[z]**2)
        # now Vd will be integrated as sum r'=inf^r E(r) dr
        # in principle Vd = 0 for r = inf,
        # but we can choose any reference we want
        # in any case, the potential in r = r_max is due
        # to the charge contained
        # in r_max:
        Vd = np.zeros(len(r), dtype=np.float64)
        Vd[len(r)-1] = 0
        # now integrate backwards
        # Vd(r) = int_inf^r E(r') dr'
        # Vd(r-h) = int_inf^r E(r') dr' + int_r^r-h E(r') dr'
        # Vd(r-h) = Vd(r) + E(r)*dr
        for z in reversed(range(0, len(r)-1)):
            Vd[z] = Vd[z+1] + E[z]*(r[z+1] - r[z])
        totalVd += Vd
    return totalVd

# calculate exchange potential 
# returns the coefficient multiplying each orbital
def getPotentialX(r, phiList, iOrb):
    totalVx = {}
    for jOrb in phiList.keys():
        if ('+' in jOrb and '-' in iOrb) or ('-' in jOrb and '+' in iOrb):
              continue
        # calculate Vex(r) * W_other(r) = int W_this(r')*W_other(r')*1/(r-r') dV W_other(r)
	# notice that, differently from Vd, the potential is multiplying W_other, not W_this
	# Define a "charge density" rho(r) = W_this(r)W_other(r)
	# 0) calculate rho(r) = W_this(r)W_other(r)
	# 1) calculate Q(r) = 4*pi*sum_r'=0^r rho(r)*r^2*dr
	# 2) calculate E(r) = Q(r)/(4*pi*r^2)
	# 3) calculate Vex(r) = sum_r'=inf^r E(r)*dr
        E = np.zeros(len(r), dtype=np.float64)
        rho = np.zeros(len(r), dtype=np.float64)
	for z in range(0, len(r)):
	    # jOrb is "other"
	    # iOrb is "this"
	    rho[z] = phiList[jOrb].rpsi[z]*phiList[iOrb].rpsi[z]
        Q = 0
        Q2 = 0
	for z in range(0, len(r)):
	    dr = 0
	    if z >= 1:
	        dr = r[z] - r[z-1]
	    else:
	        dr = r[z]
	    Q += 4*np.pi*rho[z]*r[z]**2*dr
	    # this is E:
	    E[z] = Q/(4*np.pi*r[z]**2)
        Vex = np.zeros(len(r), dtype=np.float64)
	# now Vex will be integrated as sum r'=inf^r E(r) dr
	# in principle Vex = 0 for r = inf,
	# but we can choose any reference we want
	# in any case, the potential in r = r_max is due
	# to the charge contained
	# in r_max:
	Vex[len(r)-1] = 0
	# now integrate backwards
	# Vex(r) = int_inf^r E(r') dr'
	# Vex(r-h) = int_inf^r E(r') dr' + int_r^r-h E(r') dr'
	# Vex(r-h) = Vex(r) + E(r)*dr
	for z in reversed(range(0, len(r)-1)):
            Vex[z] = Vex[z+1] + E[z]*(r[z+1] - r[z])
        totalVx[jOrb] = Vex
    return totalVx

def calculateE0(r, listPhi, vd, vxc):
    E0 = 0
    sumEV = 0
    J = 0
    K = 0
    JmK = 0
    for iOrb in listPhi.keys():
        E0 += listPhi[iOrb].E
        sumEV += listPhi[iOrb].E
	for z in range(0, len(r)):
	    dr = 0
	    if z < len(r)-1:
	        dr = r[z+1] - r[z]
	    # should have 4*pi*Y^2, but for s orbitals Y^2 = 1/4pi
            Hex = 0
            Vh = vd[z]
            for jOrb in vxc[iOrb].keys():
                #if jOrb == iOrb:
                #    Vh -= vxc[iOrb][jOrb][z]
                #    continue
                Hex += vxc[iOrb][jOrb][z]*listPhi[iOrb].rpsi[z]*listPhi[jOrb].rpsi[z]
  	    J += (Vh*listPhi[iOrb].rpsi[z]**2)*(r[z]**2)*dr
            K += Hex*(r[z]**2)*dr
  	    JmK += (Vh*listPhi[iOrb].rpsi[z]**2)*(r[z]**2)*dr - Hex*(r[z]**2)*dr
    E0 += -0.5*JmK
    return [E0, sumEV, J, K]

def getLinSyst(listPhi, r, pot, vd, vxc):
        # prepare eq. F psi = 0
        # psi is a column vector with all orbital in each r value with one extra final entry, which is the energy
        # size of psi = len(listPhi)*len(r) + 1
        # the HF equations will be written in each point in the function F
        # the final equation in F will be (sum psi^2*r^2*dr = 1)
        Nr = len(r)
        N = len(listPhi)*Nr + len(listPhi)
        idxE = len(listPhi)*Nr
        # F x is defined as:
        # (12 - 10 f_n) y_n - f_{n-1} y_{n-1} - f_{n+1} y_{n+1} + (s[i+1] + 10.0*s[i] + s[i-1]) = 0
        # we do not write F itself as it is non-linear due to the demand in the last eq.
        # we look for the eigenvalue, using Newton's method
        # given an initial vector psi = x0, we get the next one using:
        # F x = F x0 + J (x - x0)
        # F x = 0 => we should solve J delta X = - F (x0)
        # J is the jacobian => J_ij = dF_i/dx_j
    
        m = 1
    
        F0 = np.zeros(N, dtype=np.float64)
        J = np.zeros((N, N), dtype=np.float64)
        for iOrb in sorted(listPhi.keys()):
            nOrb = phiToInt[iOrb]
            l = listPhi[iOrb].l
            n = listPhi[iOrb].n
            E = listPhi[iOrb].E
    
            # calculate the extra term as \sum_j psi_j Vx_j
            # these are the linear terms due to the remainder of the potentials
            pot_full_effective = pot + vd # this multiplies the current phi[iOrb]
            if iOrb in vxc[iOrb]:
                pot_full_effective -= vxc[iOrb][iOrb]
            potIndep = np.zeros(len(r), dtype = np.float64)
            for jOrb in vxc[iOrb].keys():
                if iOrb == jOrb:
                    continue
                potIndep += listPhi[jOrb].psi*vxc[iOrb][jOrb]
    
            # (12 - 10 f_n) y_n - f_{n-1} y_{n-1} - f_{n+1} y_{n+1} + (s[i+1] + 10.0*s[i] + s[i-1]) = 0
            for ir in range(0, len(r)):
                a = 2*m*r[ir]**2*(E-pot_full_effective[ir]) - (l+0.5)**2
                f = 1 + a*dx**2/12.0
                s_coeff = (dx**2)/12.0*2*m*r[ir]**2
                s = (dx**2)/12.0*2*m*r[ir]**2*potIndep[ir]
                F0[nOrb*Nr+ir] += (12 - 10*f)*listPhi[iOrb].psi[ir] + 10.0*s
                if ir == 0:
                    F0[nOrb*Nr+ir] += -f*((Z*r[0])**(l+0.5))
                J[nOrb*Nr+ir, nOrb*Nr+ir] += (12 - 10*f)
                J[nOrb*Nr + ir, idxE + nOrb] += -10*(2*m*r[ir]**2)*(dx**2/12.0)*listPhi[iOrb].psi[ir]
                for jOrb in sorted(listPhi.keys()):
                    mOrb = phiToInt[jOrb]
                    if iOrb == jOrb:
                        continue
                    if jOrb in vxc[iOrb]:
                        J[nOrb*Nr+ir, mOrb*Nr+ir] += 10.0*s_coeff*vxc[iOrb][jOrb][ir]
                if ir > 0:
                    a = 2*m*r[ir-1]**2*(E-pot_full_effective[ir-1]) - (l+0.5)**2
                    f = 1 + a*dx**2/12.0
                    s = (dx**2)/12.0*2*m*r[ir-1]**2*potIndep[ir-1]
                    s_coeff = (dx**2)/12.0*2*m*r[ir-1]**2
                    F0[nOrb*Nr+ir] += -f*listPhi[iOrb].psi[ir-1] + s
                    J[nOrb*Nr+ir, nOrb*Nr+ir-1] += -f
                    J[nOrb*Nr + ir, idxE + nOrb] += -(2*m*r[ir-1]**2)*(dx**2/12.0)*listPhi[iOrb].psi[ir-1]
                    for jOrb in sorted(listPhi.keys()):
                        mOrb = phiToInt[jOrb]
                        if iOrb == jOrb:
                            continue
                        if jOrb in vxc[iOrb]:
                            J[nOrb*Nr+ir, mOrb*Nr+ir-1] += s_coeff*vxc[iOrb][jOrb][ir-1]
                if ir < len(r)-1:
                    a = 2*m*r[ir+1]**2*(E-pot_full_effective[ir+1]) - (l+0.5)**2
                    f = 1 + a*dx**2/12.0
                    s = (dx**2)/12.0*2*m*r[ir+1]**2*potIndep[ir+1]
                    s_coeff = (dx**2)/12.0*2*m*r[ir+1]**2
                    F0[nOrb*Nr+ir] += -f*listPhi[iOrb].psi[ir+1] + s
                    J[nOrb*Nr+ir, nOrb*Nr+ir+1] += -f
                    J[nOrb*Nr + ir, idxE + nOrb] += -(2*m*r[ir+1]**2)*(dx**2/12.0)*listPhi[iOrb].psi[ir+1]
                    for jOrb in sorted(listPhi.keys()):
                        mOrb = phiToInt[jOrb]
                        if iOrb == jOrb:
                            continue
                        if jOrb in vxc[iOrb]:
                            J[nOrb*Nr+ir, mOrb*Nr+ir+1] += s_coeff*vxc[iOrb][jOrb][ir+1]

        # (sum psi^2*r^2*dr = 1)
        for iOrb in listPhi:
            l = listPhi[iOrb].l
            n = listPhi[iOrb].n
            nOrb = phiToInt[iOrb]
            E = listPhi[iOrb].E
            for ir in range(0, len(r)):
    	        dr = 0
    	        if ir < len(r)-1:
                    dr = r[ir+1] - r[ir]
                F0[idxE + nOrb] += (listPhi[iOrb].psi[ir]*r[ir]**(-0.5))**2 * r[ir]**2 * dr
            F0[idxE + nOrb] += - 1.0
            # n = int delta(psi(x)) |psi'(x)| dx = sum_roots int delta (x - x_i) |psi'(x)| / |psi'(x_i)| dx
            for ir in range(0, len(r)):
    	        dr = 0
    	        if ir < len(r)-1:
                    dr = r[ir+1] - r[ir]
                J[idxE + nOrb, nOrb*Nr + ir] += 2*listPhi[iOrb].psi[ir]*dr*r[ir]
        nF0 = 0
        for i in range(0, len(F0)):
            nF0 += F0[i]**2

        return [J, F0, nF0, Nr, N, idxE]

class phi:
    n = 1
    l = 0
    E = -2.0
    no = 0
    psi = None
    rpsi = None
    Emax = 0.0
    Emin = -99.0
    def __init__(self, _n, _l, _E):
        self.n = _n
        self.l = _l
        self.E = _E
        self.Emax = 0.0
        self.Emin = -99.0

    def toPsi(self, r, changeInPlace = False):
        n = 0
        for i in range(0, len(self.psi)):
            self.rpsi[i] = self.psi[i]*r[i]**(-0.5) # undo y->R(r) transform
	    ip = len(r)-1
	    if i < len(r)-1:
	        ip = i+1
	    dr = np.fabs(r[ip]-r[i])
            n += (r[i]*self.rpsi[i])**2*dr        # normalise it so that int |r R(r)|^2 dr == 1
        parity = 1
        if self.rpsi[0] < 0:
            parity = -1
        if n != 0:
            for i in range(0, len(self.psi)):
                self.rpsi[i] /= parity*np.sqrt(n)
        if changeInPlace:
            self.psi = self.rpsi[:]

Z = 3
useDIIS = False

dx = 1e-1/Z
r = init(dx, Z*150, np.log(1e-4))

listPhi = {}
# create objects to hold energy and wave functions of each Hartree-Fock equation
# provide boundary conditions n, l in first arguments
# provide initial energy to use when starting to look for solutions
# propose to start with the Hydrogen-like (if Hydrogen had atomic number Z) energy level (0.5*Z^2/n^2)
listPhi['1s1+'] = phi(1, 0, -Z**2/(1.0**2)*0.5)
listPhi['1s1-'] = phi(1, 0, -Z**2/(1.0**2)*0.5)
listPhi['2s1+'] = phi(2, 0, -Z**2/(2.0**2)*0.5)
#listPhi['2s1-'] = phi(2, 0, -Z**2/(2.0**2)*0.5)

phiToInt = {}
intToPhi = {}
nOrb = 0
for i in listPhi:
    phiToInt[i] = nOrb
    intToPhi[nOrb] = i
    nOrb += 1

pot = V(r, Z)

for iOrb in listPhi.keys():
    listPhi[iOrb].psi = np.zeros(len(r), dtype=np.float64)
    listPhi[iOrb].rpsi = np.zeros(len(r), dtype=np.float64)
    n = listPhi[iOrb].n
    l = listPhi[iOrb].l
    for ir in range(0, len(r)):
        listPhi[iOrb].psi[ir] = 1e-3

Nscf = 1000

vd_last = np.zeros(len(r), dtype = np.float64)
vxc_last = {}
gamma_v = 0.9

E0_old = 0
for iSCF in range(0, Nscf):
    print "===> On SCF iteration %d" % iSCF

    if iSCF == 0:
        vd = np.zeros(len(r), dtype = np.float64)
        vd_last = vd[:]
        vxc = {}
        for iOrb in sorted(listPhi.keys()):
            nOrb = phiToInt[iOrb]
            vxc[iOrb] = {}
            vxc_last[iOrb] = {}
            for jOrb in sorted(listPhi.keys()):
                vxc[iOrb][jOrb] = np.zeros(len(r), dtype = np.float64)
                vxc_last[iOrb][jOrb] = vxc[iOrb][jOrb]
    else:
        vd = vd_last*gamma_v + getPotentialH(r, listPhi)*(1-gamma_v)
        vd_last = vd[:]
        vxc = {}
        vxc_new = {}
        for iOrb in sorted(listPhi.keys()):
            vxc_new[iOrb] = getPotentialX(r, listPhi, iOrb)
            vxc[iOrb] = {}
            for jOrb in vxc_new[iOrb]:
                vxc[iOrb][jOrb] = vxc_last[iOrb][jOrb]*gamma_v + vxc_new[iOrb][jOrb]*(1-gamma_v)
                vxc_last[iOrb][jOrb] = vxc[iOrb][jOrb]
    np.set_printoptions(threshold=np.inf)

    # Newton iterations
    # solve J dX = - F0
    minF0Sum = 1e50
    bestPhi = {}
    E0 = 0
    for iOrb in sorted(listPhi.keys()):
        listPhi[iOrb].Emin = -Z**2*0.5
        listPhi[iOrb].Emax = 0

    listDx = collections.deque(maxlen = 10)
    for iN in range(0, 2000):
        print "======> On Newton iteration %d (potential fixed here: only trying to solve linear system)" % iN

        [J, F0, nF0, Nr, N, idxE] = getLinSyst(listPhi, r, pot, vd, vxc)
        gamma = 0.1
        for item in listPhi:
            if np.fabs(listPhi[item].E)*eV < 10:
                gamma = 0.01

        print "F0: ", nF0, "minimum so far: ", minF0Sum
        finishNow = False
        if nF0 < minF0Sum:
            minF0Sum = nF0
            if iN > 10:
                finishNow = True
        #else:
        #    print "Getting out of loop as it went crazy!"
        #    break

        no_old = {}
        for iOrb in listPhi:
            no_old[iOrb] = 0
            for i in range(1, int(len(r))):
                if listPhi[iOrb].rpsi[i]*listPhi[iOrb].rpsi[i-1] < 0 and r[i] > 0.1:
                    no_old[iOrb] += 1

        dX = np.linalg.solve(J, F0)

        listDx.append(-gamma*dX)

        # use DIIS
        if useDIIS:
            B = np.zeros((len(listDx)+1, len(listDx)+1), dtype = np.float64)
            L = np.zeros(len(listDx)+1, dtype = np.float64)
            for idx in range(0, len(listDx)):
                for jdx in range(0, len(listDx)):
                    B[idx, jdx] = np.dot(listDx[idx], listDx[jdx])
            for idx in range(0, len(listDx)):
                B[len(listDx), idx] = -1
                B[idx, len(listDx)] = -1
            L[len(listDx)] = -1.0
            C = np.linalg.solve(B, L)
            print C
        
            for iOrb in listPhi:
                nOrb = phiToInt[iOrb]
                n = listPhi[iOrb].n
                for ic in range(0, len(listDx)):
                    for ir in range(0, len(r)):
                        listPhi[iOrb].psi[ir] += listDx[ic][nOrb*Nr + ir]*C[ic]
        else:
            for iOrb in listPhi:
                nOrb = phiToInt[iOrb]
                n = listPhi[iOrb].n
                for ir in range(0, len(r)):
                    #listPhi[iOrb].psi[ir] += -gamma*listPhi[iOrb].E/(-Z**2*0.5/(n**2))*dX[nOrb*Nr + ir]
                    listPhi[iOrb].psi[ir] += -gamma*dX[nOrb*Nr + ir]

        # multiply by 1/sqrt(r) to undo transformation that guarantees convergence at zero
        # and renormalise again (should already be guaranteed by last equations in J and F0, but
        # this should force this to be always true, even if we are slightly away from the true solution
        # result in listPhi[iOrb].rpsi
        for iOrb in listPhi:
            listPhi[iOrb].toPsi(r, False)

        no = {}
        for iOrb in listPhi:
            no[iOrb] = 0
            for i in range(1, int(len(r))):
                if listPhi[iOrb].rpsi[i]*listPhi[iOrb].rpsi[i-1] < 0 and r[i] > 0.1:
                    print "Zero at ", r[i]
                    no[iOrb] += 1

        for iOrb in listPhi:
            print "Old energy: ", listPhi[iOrb].E*eV, ", nodes = ", no_old[iOrb], " Emax ", listPhi[iOrb].Emax*eV, " Emin ", listPhi[iOrb].Emin*eV

        for iOrb in listPhi:
            nOrb = phiToInt[iOrb]
            n = listPhi[iOrb].n
            l = listPhi[iOrb].l
            if useDIIS and iN > 2:
                dE = 0
                for ic in range(0, len(listDx)):
                    dE += listDx[ic][idxE+nOrb]*C[ic]

            else:
                #dE = -gamma*listPhi[iOrb].E/(-Z**2*0.5/(n**2))*dX[idxE + nOrb]
                dE = -gamma*dX[idxE + nOrb]

            if no[iOrb] > nodes(listPhi[iOrb].n, listPhi[iOrb].l):
                listPhi[iOrb].Emax = listPhi[iOrb].E
                dE = (listPhi[iOrb].Emax + listPhi[iOrb].Emin)*0.5 - listPhi[iOrb].E
                listPhi[iOrb].E += dE
            elif no[iOrb] < nodes(listPhi[iOrb].n, listPhi[iOrb].l):
                listPhi[iOrb].Emin = listPhi[iOrb].E
                dE = (listPhi[iOrb].Emax + listPhi[iOrb].Emin)*0.5 - listPhi[iOrb].E
                listPhi[iOrb].E += dE
            else:
                if np.fabs(dE) > 0.1:
                    dE = 0.1*dE/np.fabs(dE)
                listPhi[iOrb].E += dE

                if dE > 0 and listPhi[iOrb].E > listPhi[iOrb].Emax:
                    listPhi[iOrb].E = listPhi[iOrb].Emax
                elif dE < 0 and listPhi[iOrb].E < listPhi[iOrb].Emin:
                    listPhi[iOrb].E = listPhi[iOrb].Emin
            print "New energy: ", listPhi[iOrb].E*eV, ", nodes = ", no[iOrb], " Emax ", listPhi[iOrb].Emax*eV, " Emin ", listPhi[iOrb].Emin*eV

        if useDIIS:
            newDx = np.zeros(N, dtype = np.float64)
            for iOrb in listPhi:
                nOrb = phiToInt[iOrb]
                for ic in range(0, len(listDx)):
                    for ir in range(0, len(r)):
                        newDx[nOrb*Nr + ir] += listDx[ic][nOrb*Nr + ir]*C[ic]
                    newDx[idxE + nOrb] += listDx[ic][idxE+nOrb]*C[ic]
            listDx[len(listDx)-1] = newDx
            print "last dx = ", listDx[len(listDx)-1]

        idx = np.where(r > 5)
        if len(idx[0]) != 0:
            idx = idx[0][0]
        else:
            idx = len(r)-1
        plt.clf()
        leg = []
        exact_p = 2*np.exp(-r)   # solution for R(r) in Hydrogen, n = 1
        col = ['r-', 'g-', 'b-', 'r-.', 'g-.', 'b-.']
        c = 0
        for iOrb in listPhi.keys():
            plt.plot(r[0:idx], listPhi[iOrb].rpsi[0:idx], col[c], label='$R_{%s}$'%iOrb)
            c += 1
            leg.append('%s (%3f eV)' % (iOrb, listPhi[iOrb].E*eV))
        plt.plot(r[0:idx], exact_p[0:idx], 'g--', label='$R_{exact}$')
        leg.append('Exact H (1s)')
    
        plt.legend(leg, frameon=False)
        plt.xlabel('$r$')
        plt.ylabel('$|R(r)|$')
        [E0, sumEV, J, K] = calculateE0(r, listPhi, vd, vxc)
        plt.title('Z=%d, SCF iter=%d, E_{0}=%4f eV'%(Z, iSCF, E0*eV))
        plt.draw()
        plt.savefig('pseudo_potentials.pdf', bbox_inches='tight')
        #plt.show()
        for iOrb in listPhi.keys():
            leg = []
            plt.clf()
            c = 0
            plt.plot(r[0:idx], vd[0:idx], col[c], label='Vd')
            leg.append('Vd')
            c += 1
            for item in vxc[iOrb]:
                plt.plot(r[0:idx], vxc[iOrb][item][0:idx], col[c], label='Vd')
                leg.append('Vxc wrt %s' % item)
                c += 1
            plt.legend(leg, frameon=False)
            plt.xlabel('$r$ [a0]')
            plt.ylabel('Potential')
            plt.title('Z=%d, SCF iter=%d, %s %f eV'%(Z, iSCF, iOrb, listPhi[iOrb].E*eV))
            plt.draw()
            plt.savefig('pot_%s.pdf' % iOrb, bbox_inches='tight')
            n = listPhi[iOrb].n
            l = listPhi[iOrb].l
            #if no[iOrb] != nodes(n, l):
            #    import sys
            #    sys.exit(0)
        print "=> Ground state calculation: E0 = %5f eV, \sum \epsilon = %5f eV, J = %5f eV, K = %5f eV" % (E0*eV, sumEV*eV, J*eV, K*eV)
        if minF0Sum < 1e-4*float(len(listPhi)) and finishNow:
            break

    if np.fabs(1 - E0_old/E0) < 1e-4 and iSCF > 5:
        print "===> Ground state energy changed by less than 1e-6 (by ", 100.0*np.fabs(1 - E0_old/E0),"%). E0 = ", E0*eV, "eV"
        break
    else:
        print "===> SCF iteration %d, E0 = %5f eV, delta E0 = %5f eV " % (iSCF, E0*eV, (E0 - E0_old)*eV)
    E0_old = E0
