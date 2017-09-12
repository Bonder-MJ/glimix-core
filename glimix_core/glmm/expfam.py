from __future__ import absolute_import, division, unicode_literals

from copy import copy

from liknorm import LikNormMachine
from numpy import exp

from optimix import Function

from ..ep import EPLinearKernel
from .glmm import GLMM


class GLMMExpFam(GLMM):
    r"""Alguma coisa.

    Example
    -------

    .. doctest::

        >>> from numpy import dot, sqrt, zeros
        >>> from numpy.random import RandomState
        >>>
        >>> from numpy_sugar.linalg import economic_qs
        >>>
        >>> from glimix_core.glmm import GLMMExpFam
        >>>
        >>> random = RandomState(0)
        >>> nsamples = 50
        >>>
        >>> X = random.randn(50, 2)
        >>> G = random.randn(50, 100)
        >>> K = dot(G, G.T)
        >>> ntrials = random.randint(1, 100, nsamples)
        >>> z = dot(G, random.randn(100)) / sqrt(100)
        >>>
        >>> successes = zeros(len(ntrials), int)
        >>> for i in range(len(ntrials)):
        ...     successes[i] = sum(z[i] + 0.2 * random.randn(ntrials[i]) > 0)
        >>>
        >>> y = (successes, ntrials)
        >>>
        >>> QS = economic_qs(K)
        >>> glmm = GLMMExpFam(y, 'binomial', X, QS)
        >>> print('Before: %.2f' % glmm.lml())
        Before: -95.19
        >>> glmm.fit(verbose=False)
        >>> print('After: %.2f' % glmm.lml())
        After: -92.24
    """

    def __init__(self, y, lik_name, X, QS):
        GLMM.__init__(self, y, lik_name, X, QS)

        self._ep = EPLinearKernel(self._X.shape[0])
        self._ep.set_compute_moments(self.compute_moments)
        self._machine = LikNormMachine(self._lik_name, 1000)
        self.update_approx = True

        self.variables().get('beta').listen(self.set_update_approx)
        self.variables().get('logscale').listen(self.set_update_approx)
        self.variables().get('logitdelta').listen(self.set_update_approx)

    def __copy__(self):
        gef = GLMMExpFam(self._y, self._lik_name, self._X, self._QS)
        gef.__dict__['_ep'] = copy(self._ep)
        gef.__dict__['_ep'].set_compute_moments(gef.compute_moments)
        gef.update_approx = self.update_approx

        super()._copy_to(gef)

        return gef

    def __del__(self):
        if hasattr(self, '_machine'):
            self._machine.finish()

    def _update_approx(self):
        if not self.update_approx:
            return

        self._ep.set_prior(self.mean(), self.covariance())
        self.update_approx = False

    @property
    def beta(self):
        return GLMM.beta.fget(self)
        # return super().beta

    @beta.setter
    def beta(self, v):
        GLMM.beta.fset(self, v)
        # super().beta = v
        self.set_update_approx()

    def compute_moments(self, eta, tau, moments):
        self._machine.moments(self._y, eta, tau, moments)

    def covariance(self):
        return dict(QS=self._QS, scale=self.scale, delta=self.delta)

    def fix(self, var_name):
        super().fix(var_name)
        self.set_update_approx()

    def gradient(self):
        self._update_approx()

        g = self._ep.lml_derivatives(self._X)
        ed = exp(-self.logitdelta)
        es = exp(self.logscale)

        grad = dict()
        grad['logitdelta'] = g['delta'] * (ed / (1 + ed)) / (1 + ed)
        grad['logscale'] = g['scale'] * es
        grad['beta'] = g['mean']

        return grad

    @property
    def logitdelta(self):
        return GLMM.logitdelta.fget(self)

    @logitdelta.setter
    def logitdelta(self, v):
        GLMM.logitdelta.fset(self, v)
        self.set_update_approx()

    @property
    def logscale(self):
        return GLMM.logscale.fget(self)

    @logscale.setter
    def logscale(self, v):
        # super().logscale = v
        GLMM.logscale.fset(self, v)
        self.set_update_approx()

    def set_update_approx(self, _=None):
        self.update_approx = True

    def set_variable_bounds(self, var_name, bounds):
        super().set_variable_bounds(var_name, bounds)
        self.set_update_approx()

    def unfix(self, var_name):
        super().unfix(var_name)
        self.set_update_approx()

    def value(self):
        self._update_approx()
        return self._ep.lml()
