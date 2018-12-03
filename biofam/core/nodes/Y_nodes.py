from __future__ import division
import numpy.ma as ma
import numpy as np
import scipy as s
import math

from biofam.core.utils import dotd
from biofam.core import gpu_utils

# Import manually defined functions
from .variational_nodes import Constant_Variational_Node

class Y_Node(Constant_Variational_Node):
    def __init__(self, dim, value):
        Constant_Variational_Node.__init__(self, dim, value)

        # Mask missing values
        self.mask()

        self.mini_batch = None

    def precompute(self, options=None):
        """ Method to precompute some terms to speed up the calculations """

        # Dimensionalities
        self.N = self.dim[0] - self.getMask().sum(axis=0)
        self.D = self.dim[1] - self.getMask().sum(axis=1)

        # GPU mode
        gpu_utils.gpu_mode = options['gpu_mode']

        # Constant ELBO terms
        self.likconst = -0.5 * s.sum(self.N) * s.log(2.*s.pi)

    def mask(self):
        """ Method to mask missing observations """
        if type(self.value) != ma.MaskedArray:
            self.value = ma.masked_invalid(self.value)
        ma.set_fill_value(self.value, 0.)

    def getMask(self):
        """ Get method for the mask """
        if self.mini_batch is None:
            return ma.getmask(self.value)
        else:
            return ma.getmask(self.mini_batch)
            

    def define_mini_batch(self, ix):
        """ Method to define a mini-batch (only for stochastic inference) """
        self.mini_batch = self.value[ix,:]

    def get_mini_batch(self):
        """ Method to retrieve a mini-batch (only for stochastic inference) """
        if self.mini_batch is None:
            return self.getExpectation()
        else:
            return self.mini_batch

    def calculateELBO(self):
        """ Method to calculate evidence lower bound """

        # Collect expectations from nodes
        Y = self.getExpectation()
        Tau = self.markov_blanket["Tau"].getExpectations()
        Wtmp = self.markov_blanket["W"].getExpectations()
        Ztmp = self.markov_blanket["Z"].getExpectations()
        W, WW = Wtmp["E"].T, Wtmp["E2"].T
        Z, ZZ = Ztmp["E"], Ztmp["E2"]
        mask = ma.getmask(self.value)

        # Mask relevant matrices
        Tau["lnE"][mask] = 0

        # Move matrices to the GPU

        ZW = Z.dot(W)
        tmp = s.square(Y) \
            + s.array(ZZ).dot(s.array(WW)) \
            - s.dot(s.square(Z),s.square(W)) + s.square(ZW) \
            - 2*ZW*Y 

        tmp[mask] = 0.

        elbo = self.likconst + 0.5*Tau["lnE"].sum() - s.sum(Tau["E"] * tmp)

        return elbo
