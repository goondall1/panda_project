#!/usr/bin/env python

######################################################################
# Software License Agreement (BSD License)
#
#  Copyright (c) 2010, Rice University
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#   * Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above
#     copyright notice, this list of conditions and the following
#     disclaimer in the documentation and/or other materials provided
#     with the distribution.
#   * Neither the name of the Rice University nor the names of its
#     contributors may be used to endorse or promote products derived
#     from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
#  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
#  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
#  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
#  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
#  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.
######################################################################

# Author: Mark Moll

from math import sin, cos
from functools import partial
import numpy as np
try:
    from ompl import base as ob
    from ompl import control as oc
except ImportError:
    # if the ompl module is not in the PYTHONPATH assume it is installed in a
    # subdirectory of the parent directory called "py-bindings."
    from os.path import abspath, dirname, join
    import sys
    sys.path.insert(0, join(dirname(dirname(abspath(__file__))), 'py-bindings'))
    from ompl import base as ob
    from ompl import control as oc

## @cond IGNORE
# a decomposition is only needed for SyclopRRT and SyclopEST
class MyDecomposition(oc.GridDecomposition):
    def __init__(self, length, bounds):
        super(MyDecomposition, self).__init__(length, 2, bounds)
    def project(self, s, coord):
        coord[0] = s.getX()
        coord[1] = s.getY()
    def sampleFullState(self, sampler, coord, s):
        sampler.sampleUniform(s)
        s.setXY(coord[0], coord[1])
## @endcond

def isStateValid(spaceInformation, state):
    # perform collision checking or check if other constraints are
    # satisfied
    return spaceInformation.satisfiesBounds(state)

def propagate(start, control, duration, state):
    state.setX(start.getX() + control[0] * duration * cos(start.getYaw()))
    state.setY(start.getY() + control[0] * duration * sin(start.getYaw()))
    state.setYaw(start.getYaw() + control[1] * duration)

def plan():
    # construct the state space we are planning in
    space = ob.SE2StateSpace()

    # set the bounds for the R^2 part of SE(2)
    bounds = ob.RealVectorBounds(2)
    bounds.setLow(-1)
    bounds.setHigh(1)

    space.setBounds(bounds)

    # create a control space
    cspace = oc.RealVectorControlSpace(space, 2)

    # set the bounds for the control space
    cbounds = ob.RealVectorBounds(2)
    cbounds.setLow(-.3)
    cbounds.setHigh(.3)
    cspace.setBounds(cbounds)

    # define a simple setup class
    ss = oc.SimpleSetup(cspace)
    ss.setStateValidityChecker(ob.StateValidityCheckerFn( \
        partial(isStateValid, ss.getSpaceInformation())))
    ss.setStatePropagator(oc.StatePropagatorFn(propagate))

    # create a start state
    start = ob.State(space)
    start().setX(-0.5)
    start().setY(0.0)
    start().setYaw(0.0)

    # create a goal state
    goal = ob.State(space)
    goal().setX(0.0)
    goal().setY(0.5)
    goal().setYaw(0.0)

    start_goal_pairs = get_fixed_start_goal_pairs(bounds)
    starts , goals = [] , []
    for i, (s, g) in enumerate(start_goal_pairs):
        if i == 100:
            # create a start state
            start = ob.State(space)
            start().setX(s[0])
            start().setY(s[1])
            start().setYaw(0.0)

            # create a goal state
            goal = ob.State(space)
            goal().setX(g[0])
            goal().setY(g[1])
            goal().setYaw(0.0)
            print("low[0], high[0]",bounds.low[0] ,bounds.high[0])

            # set the start and goal states
            ss.setStartAndGoalStates(start, goal, 0.05)

            # (optionally) set planner
            si = ss.getSpaceInformation()
            planner = oc.RRT(si)
            #planner = oc.EST(si)
            #planner = oc.KPIECE1(si) # this is the default
            # SyclopEST and SyclopRRT require a decomposition to guide the search
            # decomp = MyDecomposition(32, bounds)
            # planner = oc.SyclopEST(si, decomp)
            #planner = oc.SyclopRRT(si, decomp)
            ss.setPlanner(planner)
            # (optionally) set propagation step size
            si.setPropagationStepSize(.1)

            # attempt to solve the problem
            solved = ss.solve(20.0)

            if solved:
                # print the path to screen
                print("start: ", start, "goal: ", goal)
                print("Found solution:\n%s" % ss.getSolutionPath().printAsMatrix())

def _rec_all_states(state_index, grid_marks, bounds):
    dim = 2
    s = np.linspace(bounds.low[0], bounds.high[0], grid_marks)
    if state_index == dim - 1:
        return [[x] for x in s]
    next_res = _rec_all_states(state_index + 1, grid_marks, bounds)
    return [[x] + l[:] for l in next_res for x in s]

def get_fixed_start_goal_pairs(bounds):
    all_pairs = []
    grid_marks = 11
    while len(all_pairs) < 1000:
        grid_states = _rec_all_states(0, grid_marks, bounds)
        grid_states = [s for s in grid_states if is_free(s, bounds)]
        all_pairs = [(np.array(s1), np.array(s2)) for s1 in grid_states for s2 in grid_states]
        grid_marks += 1
    return all_pairs

def is_free(coordinates, bounds):
    # check if in bounds
    if any(np.abs(coordinates) >= bounds.high[0]):
        return False
    # check collision of robot with obstacles
    # robot = Point(coordinates)
    # if any([robot.intersection(obstacle) for obstacle in self.obstacles]):
    #     return False
    return True

if __name__ == "__main__":
    plan()
