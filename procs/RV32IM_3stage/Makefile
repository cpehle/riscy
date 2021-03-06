
# Copyright (c) 2016 Massachusetts Institute of Technology

# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

PROC=RV32IM_3stage

CONNECTALFLAGS += -D CONFIG_RV32
# Use a 32-bit data bus for shared memory in connectal
CONNECTALFLAGS += -D DataBusWidth=32

ACCELERATORS=DebugAccel

# This processor can be configured as an RV64 processor by uncommenting these
# two lines below and commenting out the two lines above.
# CONNECTALFLAGS += -D CONFIG_RV64
# CONNECTALFLAGS += -D DataBusWidth=64

CONNECTALFLAGS += -D CONFIG_M
CONNECTALFLAGS += -D CONFIG_S
CONNECTALFLAGS += -D CONFIG_U
CONNECTALFLAGS += -D CONFIG_ACCESS_USING_EXT_IFC
CONNECTALFLAGS += -D CONFIG_START_PC_0

# Suppress "duplicate folder" and "unfolding over ... steps" warnings
# CONNECTALFLAGS += --bscflags=" -suppress-warnings S0073:G0024 "

# Attempt to optimize the generated Verilog. In a small test with part of the
# decoder, this increased the post-synthesis area by 10% so we don't use these
# flags by default.
# CONNECTALFLAGS += --bscflags=" -opt-undetermined-vals -unspecified-to X "

include $(RISCY_HOME)/procs/Makefile.procs
