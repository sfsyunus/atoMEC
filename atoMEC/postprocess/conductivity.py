import numpy as np
from math import factorial
from scipy.special import lpmv
from scipy.integrate import quad
import sys

# from functools import cache
import functools

from atoMEC import writeoutput


"""Kubo-Greenwood conductivity etc"""


################################################################
# functions to compute various integrals of legendre functions #
################################################################


class KuboGreenwood:
    def __init__(self, orbitals, valence_orbs=[], nmax=0, lmax=0):

        self._orbitals = orbitals
        self._xgrid = orbitals._xgrid
        self._eigfuncs = orbitals._eigfuncs
        self._eigvals = orbitals.eigvals
        self._occnums = orbitals.occnums
        self._DOS_w = orbitals.DOS * orbitals.kpt_int_weight
        nbands, self._spindims, lmax_default, nmax_default = np.shape(self._eigvals)
        if nmax == 0:
            self._nmax = nmax_default
        else:
            self._nmax = nmax
        if lmax == 0:
            self._lmax = lmax_default
        else:
            self._lmax = lmax
        self.valence_orbs = valence_orbs

    @property
    def all_orbs(self):
        r"""list of tuples: all the possible orbital pairings."""
        all_orbs_tmp = []
        for l in range(self._lmax):
            for n in range(self._nmax):
                all_orbs_tmp.append((l, n))
        self._all_orbs = all_orbs_tmp
        return self._all_orbs

    @property
    def cond_orbs(self):
        r"""list of tuples: all the conduction band orbital pairings."""
        cond_orbs_tmp = self.all_orbs
        for val_orbs in self.valence_orbs:
            cond_orbs_tmp.remove(val_orbs)
        self._cond_orbs = cond_orbs_tmp
        return self._cond_orbs

    @property
    def sig_tot(self):
        r"""ndarray: the integrated total conductivity."""
        self._sig_tot = self.calc_sig(
            self.R1_int_tt, self.R2_int_tt, self.all_orbs, self.all_orbs
        )
        return self._sig_tot

    @property
    def sig_cc(self):
        r"""ndarray: the integrated cc conductivity component."""
        self._sig_cc = self.calc_sig(
            self.R1_int_cc, self.R2_int_cc, self.cond_orbs, self.cond_orbs
        )
        return self._sig_cc

    @property
    def sig_vv(self):
        r"""ndarray: the integrated vv conductivity component."""
        self._sig_vv = self.calc_sig(
            self.R1_int_vv, self.R2_int_vv, self.valence_orbs, self.valence_orbs
        )
        return self._sig_vv

    @property
    def sig_cv(self):
        r"""ndarray: the integrated cv conductivity component."""
        self._sig_cv = self.calc_sig(
            self.R1_int_cv, self.R2_int_cv, self.cond_orbs, self.valence_orbs
        )
        return self._sig_cv

    @property
    def N_tot(self):
        r"""float: the total electron number from TRK sum-rule."""
        self._N_tot = self.sig_tot * (2 * self.sph_vol / np.pi)
        return self._N_tot

    @property
    def N_free(self):
        r"""float: the free electron number from TRK sum-rule."""
        self._N_free = self.sig_cc * (2 * self.sph_vol / np.pi)
        return self._N_free

    @property
    def sph_vol(self):
        r"""float: the volume of the sphere."""
        rmax = np.exp(self._xgrid)[-1]
        V = (4.0 / 3.0) * np.pi * rmax ** 3.0
        return V

    def cond_tot(self, component="tt", gamma=0.01, maxfreq=50, nfreq=200):
        """
        Calculate the chosen component of dynamical electrical conductivity sig(w).

        Parameters
        ----------
        component : str, optional
            the desired component of the conducivity e.g. "cc", "tt" etc
        gamma : float, optional
            smoothing factor
        maxfreq : float, optional
            maximum frequency to scan up to
        nfreq : int, optional
            number of points in the frequency grid

        Returns
        -------
        cond_tot_ : ndarray
            dynamical electrical conductivity
        """

        if component == "tt":
            R1_int = self.R1_int_tt
            R2_int = self.R2_int_tt
            orb_subset_1 = self.all_orbs
            orb_subset_2 = self.all_orbs
        elif component == "cc":
            R1_int = self.R1_int_cc
            R2_int = self.R2_int_cc
            orb_subset_1 = self.cond_orbs
            orb_subset_2 = self.cond_orbs
        elif component == "cv":
            R1_int = self.R1_int_cv
            R2_int = self.R2_int_cv
            orb_subset_1 = self.cond_orbs
            orb_subset_2 = self.valence_orbs
        elif component == "vv":
            R1_int = self.R1_int_vv
            R2_int = self.R2_int_vv
            orb_subset_1 = self.valence_orbs
            orb_subset_2 = self.valence_orbs
        else:
            sys.exit("Component of conducivity not recognised")

        cond_tot_ = self.calc_sig_func(
            R1_int, R2_int, orb_subset_1, orb_subset_2, maxfreq, nfreq, gamma
        )
        return cond_tot_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R1_int_tt(self):
        R1_int_tt_ = calc_R1_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.all_orbs,
            self.all_orbs,
        )
        return R1_int_tt_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R1_int_cc(self):
        R1_int_cc_ = calc_R1_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.cond_orbs,
            self.cond_orbs,
        )
        return R1_int_cc_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R1_int_cv(self):
        R1_int_cv_ = calc_R1_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.cond_orbs,
            self.valence_orbs,
        )
        return R1_int_cv_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R1_int_vv(self):
        R1_int_vv_ = calc_R1_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.valence_orbs,
            self.valence_orbs,
        )
        return R1_int_vv_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R2_int_tt(self):
        R2_int_tt_ = calc_R2_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.all_orbs,
            self.all_orbs,
        )
        return R2_int_tt_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R2_int_cc(self):
        R2_int_cc_ = calc_R2_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.cond_orbs,
            self.cond_orbs,
        )
        return R2_int_cc_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R2_int_cv(self):
        R2_int_cv_ = calc_R2_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.cond_orbs,
            self.valence_orbs,
        )
        return R2_int_cv_

    @property
    # @functools.lru_cache
    # @writeoutput.timing
    def R2_int_vv(self):
        R2_int_vv_ = calc_R2_int_mat(
            self._eigfuncs,
            self._occnums,
            self._xgrid,
            self.valence_orbs,
            self.valence_orbs,
        )
        return R2_int_vv_

    def check_sum_rule(self, l, n, m):
        r"""
        Check the sum rule (see notes) for an orbital :math:`\phi_{nlm}` is satisfied.

        Parameters
        ----------
        l : int
            angular quantum number
        n : int
            principal quantum number
        m : int
            magnetic quantum number

        Returns
        -------
        sum_mom : ndarray
            the momentum sum rule (see notes)

        Notes
        -----
        The expression for the momentum sum rule is given by

        .. math::
            S_{p} = \sum_{(n_1,l_1,m_1)\neq (n,l,m)}\
            \frac{|\langle\phi_{nlm}|\nabla|\phi_{n_1 l_1 m_1}\rangle|^2} {\
            \epsilon_{n_1,l_1,m_1}-\epsilon_{n,l,m}}

        If the sum rule is satisfied, the summation above should equal 1/2.
        See Eq. (38) of Ref. [7]_ for an explanation of this sum rule.

        References
        ----------
        .. [7] Calderin, L. et al, Kubo--Greenwood electrical conductivity formulation
           and implementation for projector augmented wave datasets", Comp. Phys Comms.
           221 (2017): 118-142.
           `DOI:doi.org/10.1016/j.cpc.2017.08.008
           <https://doi.org/10.1016/j.cpc.2017.08.008>`__.
        """

        # set up the orbitals to sum over
        new_orbs = self.all_orbs
        new_orbs.remove((l, n))

        # initialize sum_mom and various indices
        nbands, nspin, lmax, nmax = np.shape(self._eigvals)
        sum_mom = np.zeros((nbands))

        # compute the sum rule
        for k in range(nbands):
            for l1, n1 in new_orbs:
                # the eigenvalue difference
                eig_diff = self._eigvals[k, 0, l1, n1] - self._eigvals[k, 0, l, n]
                # only states with |l-l_1|=1 contribute
                if abs(l1 - l) != 1:
                    continue
                else:
                    # scale eigenfunctions by sqrt(4 pi) due to different normalization
                    orb_l1n1 = np.sqrt(4 * np.pi) * self._eigfuncs[k, 0, l1, n1]
                    orb_ln = np.sqrt(4 * np.pi) * self._eigfuncs[k, 0, l, n]

                    # compute the matrix element <\phi|\grad|\phi> and its complex conjugate
                    if abs(m) > l1:
                        mel_sq = 0
                    else:
                        mel = calc_mel_kgm(
                            orb_ln, orb_l1n1, l, n, l1, n1, m, self._xgrid
                        )
                        mel_cc = calc_mel_kgm(
                            orb_l1n1, orb_ln, l1, n1, l, n, m, self._xgrid
                        )
                        mel_sq = np.abs(mel_cc * mel)
                    sum_mom[k] += mel_sq / eig_diff

        return sum_mom

    def calc_sig(self, R1_int, R2_int, orb_subset_1, orb_subset_2):
        r"""
        Compute the *integrated* dynamical conducivity for given subsets (see notes).

        Parameters
        ----------
        R1_int : ndarray
            the 'R1' radial component of the integrand (see notes)
        R2_int : ndarray
            the 'R2' radial component of the integrand (see notes)
        orb_subset_1 : list of tuples
            the first subset of orbitals to sum over
        orb_subset_2 : list of tuples
            the second subset of orbitals to sum over

        Returns
        -------
        sig : float
            the integrated dynamical conductivity

        Notes
        -----
        This function returns the integrated dynamical conductivity,
        :math:`\bar{\sigma}=\int_0^\infty d\omega \sigma(\omega)`. The conductivity
        :math:`\sigma(\omega)` is defined as

        .. math::
            \sigma_{S_1,S2}(\omega) = \frac{2\pi}{3V\omega}
            \sum_{i\in S_1}\sum_{j\in S_2} (f_i - f_j)\
            |\langle\phi_{i}|\nabla|\phi_{j}\rangle|^2\delta(\epsilon_j-\epsilon_i-\omega),

        where :math:`S_1,S_2` denote the subsets of orbitals specified in the function's
        paramaters, e.g. the conduction-conduction orbitals.

        In practise, the integral in the above equation is given by a discrete sum due
        to the presenence of the dirac-delta function.

        The paramaters `R1_int` and `R2_int` refer to radial integral components in the
        calculation of the matrix elements. See the supplementary information of
        Ref. [8]_ for more information on thse components, and the functions
        `calc_R1_int_mat` and `calc_R2_int_mat` for their definitions.

        References
        ----------
        .. [8] Callow, T.J. et al.,  "Accurate and efficient computation of mean
           ionization states with an average-atom Kubo-Greenwood approach."
           arXiv preprint arXiv:2203.05863 (2022).
           `<https://arxiv.org/abs/2203.05863>`__.
        """

        # get matrix dimensions
        nbands, nspin, lmax, nmax = np.shape(self._occnums)

        # compute the angular integrals (see functions for defns)
        P2_int = P_mat_int(2, lmax)
        P4_int = P_mat_int(4, lmax)

        # compute the products of the radial and angular integrals
        tmp_mat_1 = np.einsum("kabcd,ace->kabcde", R1_int, P2_int)
        tmp_mat_2 = np.einsum("kabcd,ace->kabcde", R2_int, P4_int)
        tmp_mat_3 = np.einsum("kcdab,cae->kabcde", R1_int, P2_int)
        tmp_mat_4 = np.einsum("kcdab,cae->kabcde", R2_int, P4_int)

        # compute the sum over the matrix element |< phi_nlm | nabla | phi_pqm >|^2
        mel_sq_mat = np.sum(
            np.abs((tmp_mat_1 + tmp_mat_2) * (tmp_mat_3 + tmp_mat_4)),
            axis=-1,
        )

        # compute the f_nl - f_pq matrix
        occ_diff_mat = calc_occ_diff_mat(self._occnums, orb_subset_1, orb_subset_2)
        # compute the (e_nl - e_pq)^-1 matrix
        eig_diff_mat = calc_eig_diff_mat(self._eigvals, orb_subset_1, orb_subset_2)

        # put it all together for the integrated conducivity
        sig_bare = np.einsum(
            "kln,klnpq->", self._DOS_w[:, 0], mel_sq_mat * occ_diff_mat / eig_diff_mat
        )

        # multiply by prefactor 2*pi/V
        sig = 2 * np.pi * sig_bare / self.sph_vol

        return sig

    def calc_sig_func(
        self, R1_int, R2_int, orb_subset_1, orb_subset_2, omega_max, n_freq, gamma
    ):

        nbands, nspin, lmax, nmax = np.shape(self._occnums)

        P2_int = P_mat_int(2, lmax)
        P4_int = P_mat_int(4, lmax)

        tmp_mat_1 = np.einsum("kabcd,ace->kabcde", R1_int, P2_int)
        tmp_mat_2 = np.einsum("kabcd,ace->kabcde", R2_int, P4_int)
        tmp_mat_3 = np.einsum("kcdab,cae->kabcde", R1_int, P2_int)
        tmp_mat_4 = np.einsum("kcdab,cae->kabcde", R2_int, P4_int)

        occ_diff_mat = calc_occ_diff_mat(self._occnums, orb_subset_1, orb_subset_2)
        eig_diff_mat = calc_eig_diff_mat(self._eigvals, orb_subset_1, orb_subset_2)

        mel_sq_mat = np.sum(
            np.abs((tmp_mat_1 + tmp_mat_2) * (tmp_mat_3 + tmp_mat_4)),
            axis=-1,
        )

        # omega_arr = np.logspace(-5, np.log(omega_max), n_freq)
        omega_0 = 1e-5
        omega_arr = np.linspace(omega_0, np.sqrt(omega_max), n_freq) ** 2
        # omega_arr = np.linspace(omega_0, omega_max, n_freq)
        sig_omega = np.zeros((np.size(omega_arr), 2))
        omega_dummy_mat = np.ones((nbands, lmax, nmax, lmax, nmax, n_freq))
        eig_diff_omega_mat = np.einsum(
            "nijkl,nijklm->nijklm", eig_diff_mat, omega_dummy_mat
        )
        eig_diff_lorentz_mat = lorentzian(omega_arr, eig_diff_omega_mat, gamma)

        mat1 = np.einsum(
            "kln,klnpq->klnpq", self._DOS_w[:, 0], mel_sq_mat * occ_diff_mat
        )
        mat2 = eig_diff_lorentz_mat / eig_diff_omega_mat

        sig_omega[:, 1] = (
            np.einsum("nijkl,nijklm->m", mat1, mat2) * 2 * np.pi / self.sph_vol
        )
        sig_omega[:, 0] = omega_arr

        N_tot = self.sig_to_N(np.trapz(sig_omega[:, 1], x=omega_arr), self.sph_vol)

        return sig_omega, N_tot

    @staticmethod
    def sig_to_N(sig, V):
        return sig * (2 * V / np.pi)


def sph_ham_coeff(l, m):
    r"""The coefficients of spherical harmonic functions"""
    c_lm = np.sqrt((2 * l + 1) * factorial(l - m) / (factorial(l + m) * 4 * np.pi))
    return c_lm


def P_mat_int(func_int, lmax):

    P_mat = np.zeros((lmax, lmax, 2 * lmax + 1))

    for l1 in range(lmax):
        for l2 in range(lmax):
            if abs(l1 - l2) == 1:
                lsmall = min(l1, l2)
                for m in range(-lsmall, lsmall + 1):
                    P_mat[l1, l2, lsmall + m] = P_int(func_int, l1, l2, m)
            else:
                continue
    return P_mat


def P_int(func_int, l1, l2, m):
    r"""The P2 integral"""

    if func_int == 2:
        integ = quad(P2_func, -1, 1, args=(l1, l2, m))[0]
    elif func_int == 4:
        integ = quad(P4_func, -1, 1, args=(l1, l2, m))[0]

    return 2 * np.pi * sph_ham_coeff(l1, m) * sph_ham_coeff(l2, m) * integ


def P2_func(x, l1, l2, m):
    r"""Input functional for P2_int"""

    return x * lpmv(m, l1, x) * lpmv(m, l2, x)


def P4_func(x, l1, l2, m):
    r"""Input functional for P4_int"""

    if (l2 + m) != 0:
        factor = (l2 + m) * lpmv(m, l2 - 1, x) - l2 * x * lpmv(m, l2, x)
    else:
        factor = -l2 * x * lpmv(m, l2, x)

    return lpmv(m, l1, x) * factor


# jit
@writeoutput.timing
# @functools.cache
def calc_R1_int_mat(eigfuncs, occnums, xgrid, orb_subset_1, orb_subset_2):
    r"""Compute the R1 integral."""

    # take the derivative of orb2
    # compute the gradient of the orbitals
    deriv_orb2 = np.gradient(eigfuncs, xgrid, axis=-1, edge_order=2)

    # chain rule to convert from dP_dx to dX_dr
    grad_orb2 = np.exp(-1.5 * xgrid) * (deriv_orb2 - 0.5 * eigfuncs)

    # initiliaze the matrix
    nbands, nspin, lmax, nmax = np.shape(occnums)
    R1_mat = np.zeros((nbands, lmax, nmax, lmax, nmax), dtype=np.float32)

    # integrate over the sphere
    for l1, n1 in orb_subset_1:
        for l2, n2 in orb_subset_2:
            if abs(l1 - l2) != 1:
                continue
            else:

                R1_mat[:, l1, n1, l2, n2] = R1_int_term(
                    eigfuncs[:, 0, l1, n1], grad_orb2[:, 0, l2, n2], xgrid
                )

                if orb_subset_1 != orb_subset_2:

                    R1_mat[:, l2, n2, l1, n1] = R1_int_term(
                        eigfuncs[:, 0, l2, n2], grad_orb2[:, 0, l1, n1], xgrid
                    )

    return R1_mat


def R1_int_term(eigfunc, grad_orb2, xgrid):

    func_int = eigfunc * np.exp(-xgrid / 2.0) * grad_orb2

    mat_ele = 4 * np.pi * np.trapz(np.exp(3.0 * xgrid) * func_int, xgrid)

    return mat_ele


# jit
@writeoutput.timing
def calc_R2_int_mat(eigfuncs, occnums, xgrid, orb_subset_1, orb_subset_2):
    r"""Compute the R2 integral."""

    # initiliaze the matrix
    nbands, nspin, lmax, nmax = np.shape(occnums)
    R2_mat = np.zeros((nbands, lmax, nmax, lmax, nmax), dtype=np.float32)

    # integrate over the sphere
    for l1, n1 in orb_subset_1:
        for l2, n2 in orb_subset_2:
            if abs(l1 - l2) != 1:
                continue
            else:
                R2_mat[:, l1, n1, l2, n2] = R2_int_term(
                    eigfuncs[:, 0, l1, n1], eigfuncs[:, 0, l2, n2], xgrid
                )

                if orb_subset_1 != orb_subset_2:

                    R2_mat[:, l2, n2, l1, n1] = R2_int_term(
                        eigfuncs[:, 0, l2, n2], eigfuncs[:, 0, l1, n1], xgrid
                    )

    return R2_mat


def R2_int_term(eigfunc_1, eigfunc_2, xgrid):

    mat_ele = 4 * np.pi * np.trapz(np.exp(xgrid) * eigfunc_1 * eigfunc_2, xgrid)

    return mat_ele


# jit
@writeoutput.timing
def calc_occ_diff_mat(occnums, orb_subset_1, orb_subset_2):

    nbands, nspin, lmax, nmax = np.shape(occnums)
    occ_diff_mat = np.zeros((nbands, lmax, nmax, lmax, nmax), dtype=np.float32)

    for k in range(nbands):
        for l1, n1 in orb_subset_1:
            for l2, n2 in orb_subset_2:
                occ_diff = -(occnums[k, 0, l1, n1] - occnums[k, 0, l2, n2])
                if abs(l1 - l2) != 1:
                    continue
                elif occ_diff < 0:
                    continue
                else:
                    occ_diff_mat[k, l1, n1, l2, n2] = occ_diff
    return occ_diff_mat


# jit
@writeoutput.timing
def calc_eig_diff_mat(eigvals, orb_subset_1, orb_subset_2):

    nbands, nspin, lmax, nmax = np.shape(eigvals)
    eig_diff_mat = np.zeros((nbands, lmax, nmax, lmax, nmax), dtype=np.float32)
    eig_diff_mat += 1e-6

    for k in range(nbands):
        for l1, n1 in orb_subset_1:
            for l2, n2 in orb_subset_2:
                if abs(l1 - l2) != 1:
                    continue
                elif eigvals[k, 0, l1, n1] - eigvals[k, 0, l2, n2] < 0:
                    continue
                else:
                    eig_diff_mat[k, l1, n1, l2, n2] = (
                        eigvals[k, 0, l1, n1] - eigvals[k, 0, l2, n2]
                    )
    return eig_diff_mat


def calc_R1_int(orb1, orb2, xgrid):
    r"""Compute the R1 integral."""

    # take the derivative of orb2
    # compute the gradient of the orbitals
    deriv_orb2 = np.gradient(orb2, xgrid, axis=-1, edge_order=2)

    # chain rule to convert from dP_dx to dX_dr
    grad_orb2 = np.exp(-1.5 * xgrid) * (deriv_orb2 - 0.5 * orb2)

    # integrate over the sphere
    func_int = orb1 * np.exp(-xgrid / 2.0) * grad_orb2
    return np.trapz(np.exp(3.0 * xgrid) * func_int, xgrid)


def calc_R2_int(orb1, orb2, xgrid):
    r"""Compute the R2 integral."""

    func_int = np.exp(xgrid) * orb1 * orb2

    return np.trapz(func_int, xgrid)


def calc_mel_kgm(orb_l1n1, orb_l2n2, l1, n1, l2, n2, m, xgrid):

    R1_int = calc_R1_int(orb_l1n1, orb_l2n2, xgrid)
    R2_int = calc_R2_int(orb_l1n1, orb_l2n2, xgrid)

    mel_tot = 0.0
    mel_tot += R1_int * P_int(2, l1, l2, m)
    mel_tot += R2_int * P_int(4, l1, l2, m)

    return mel_tot


def lorentzian(x, x0, gamma):

    # prefac = x / (x ** 2 + gamma ** 2)
    prefac = 1.0
    # prefac = 1 / x
    return (gamma / np.pi) * (prefac / (gamma ** 2 + (x - x0) ** 2))


def prod_eigfuncs(phi0, phi1, xgrid):

    return 4 * np.pi * np.trapz(np.exp(2.0 * xgrid) * phi0 * phi1, xgrid)


def proj_eigfuncs(phi0, phi1, xgrid):

    return (prod_eigfuncs(phi0, phi1, xgrid) / prod_eigfuncs(phi0, phi0, xgrid)) * phi0


# @writeoutput.timing
def gs_ortho(eigfuncs, xgrid):

    nbands, nspin, lmax, nmax, ngrid = np.shape(eigfuncs)
    eigfuncs_ortho = np.zeros_like(eigfuncs)
    norm = np.zeros_like(eigfuncs)

    for k in range(nbands):
        for sp in range(nspin):
            for l in range(lmax):
                for n1 in range(nmax):
                    eigfuncs_ortho[k, sp, l, n1] = eigfuncs[k, sp, l, n1]
                    for n2 in range(n1):
                        eigfuncs_ortho[k, sp, l, n1] -= proj_eigfuncs(
                            eigfuncs_ortho[k, sp, l, n2],
                            eigfuncs[k, sp, l, n1],
                            xgrid,
                        )
                    norm[k, sp, l, n1] = prod_eigfuncs(
                        eigfuncs_ortho[k, sp, l, n1],
                        eigfuncs_ortho[k, sp, l, n1],
                        xgrid,
                    )

    a = norm ** (-0.5)
    eigfuncs_ortho = eigfuncs_ortho * a

    return eigfuncs_ortho


"""            \sum_{(n_1,l_1,m_1) (\neq n,l,m)}\
            \frac{|\langle{\phi_{nlm}|\nabla|\phi_{n_1,l_1,m_1}\rangle|^2}\
            {\epsilon_{n_1,l_1,m_1}-\epsilon_{n,l,m}}"""
