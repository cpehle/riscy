#!/usr/bin/env python3
# coding=utf-8

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

import copy
import functools
import os
import sys

license = '''
// Copyright (c) 2016 Massachusetts Institute of Technology

// Permission is hereby granted, free of charge, to any person
// obtaining a copy of this software and associated documentation
// files (the "Software"), to deal in the Software without
// restriction, including without limitation the rights to use, copy,
// modify, merge, publish, distribute, sublicense, and/or sell copies
// of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:

// The above copyright notice and this permission notice shall be
// included in all copies or substantial portions of the Software.

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
// EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
// MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
// NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
// BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
// ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
// CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
// SOFTWARE.
'''

def read_file(filename):
    results = []
    with open(filename, 'r') as f:
        for line in f:
            # remove comments and extra whitespace
            line = line.split('#', 1)[0]
            line = line.strip()
            # only look at non-empty lines
            if len(line) != 0:
                tokens = line.split()
                results.append(tokens)
    return results

def bsv_match_mask_val(match, mask, width):
    assert match & mask == match, "match has bits that aren't set in mask"
    assert mask >> width == 0, 'mask is wider than width'
    bsv_val = ''
    for i in range(width):
        if (mask >> i) & 1 == 1:
            if (match >> i) & 1 == 1:
                bsv_val = '1' + bsv_val
            else:
                bsv_val = '0' + bsv_val
        else:
            bsv_val = '?' + bsv_val
    bsv_val = str(width) + "'b" + bsv_val
    return bsv_val

def get_inst_types(args):
    def get_reg_type(reg, args):
        if reg in args:
            return 'i'
        elif 'f' + reg in args:
            return 'f'
        else:
            return 'n'
    def get_imm_type(args):
        imm_mapping = {
                'imm20'   : 'U',
                'oimm20'  : 'U',
                'jimm20'  : 'UJ',
                'imm12'   : 'I',
                'oimm12'  : 'I',
                'simm12'  : 'S',
                'sbimm12' : 'SB',
                'zimm'    : 'Z',
                'shamt5'  : 'I',
                'shamt6'  : 'I'
                }
        for imm_name in imm_mapping:
            if imm_name in args:
                return imm_mapping[imm_name]
        return 'None'

    rd  = get_reg_type('rd',  args)
    rs1 = get_reg_type('rs1', args)
    rs2 = get_reg_type('rs2', args)
    rs3 = get_reg_type('rs3', args)
    imm = get_imm_type(args)

    return (rd, rs1, rs2, rs3, imm)

class RiscvOperand:
    def __init__(self, operand_row):
        self.name = operand_row[0]
        self.bit_string = operand_row[1]
        self.operand_type = operand_row[2]
        self.description = operand_row[3]

        # parse bit_string
        if '[' in self.bit_string:
            # we have an immediate value
            inst_bits = []
            imm_bits = []
            for bitrange in self.bit_string.split(','):
                # we have something like a:b[x:y|z] or a[x]
                raw_inst_bits = bitrange.split('[')[0]
                raw_imm_bits = bitrange.split('[')[1].split(']')[0]
                if ':' in raw_inst_bits:
                    lrange, rrange = raw_inst_bits.split(':')
                    inst_bits += range(int(lrange), int(rrange)-1, -1)
                else:
                    inst_bits += [int(raw_inst_bits)]
                for y in raw_imm_bits.split('|'):
                    if ':' in y:
                        lrange, rrange = y.split(':')
                        imm_bits += range(int(lrange), int(rrange)-1, -1)
                    else:
                        imm_bits += [int(y)]

            # create bit_map dictionary
            bit_map = {}
            for i in range(len(inst_bits)):
                bit_map[imm_bits[i]] = inst_bits[i]

            # construct self.inst_bit_string
            first_bit = True
            i = 31
            while i >= 0:
                if i in bit_map:
                    # look for sequential bits
                    starting_i = i
                    while i > 0 and i-1 in bit_map and bit_map[i-1] == bit_map[i]-1:
                        i -= 1
                    # prepare inst_bit_string
                    if first_bit:
                        self.inst_bit_string = '{'
                        first_bit = False
                    else:
                        self.inst_bit_string += ', '
                    # add inst[] to inst_bit_string
                    if starting_i == i:
                        # one bit
                        self.inst_bit_string += "inst[%d]" % bit_map[i]
                    else:
                        # multiple bits
                        self.inst_bit_string += "inst[%d:%d]" % (bit_map[starting_i], bit_map[i])
                    i -= 1
                elif not first_bit:
                    # count sequential zero bits
                    length = 0
                    while i >= 0 and i not in bit_map:
                        i -= 1
                        length += 1
                    self.inst_bit_string += ", %d'b0" % length
                else:
                    i -= 1
            self.inst_bit_string += '}'

            if self.is_simm():
                self.inst_bit_string = 'signExtend(%s)' % self.inst_bit_string
            elif self.is_uimm():
                self.inst_bit_string = 'zeroExtend(%s)' % self.inst_bit_string
        else:
            self.inst_bit_string = 'inst[' + self.bit_string + ']'

    def is_imm(self):
        return self.operand_type == 'simm' or self.operand_type == 'offset' or self.operand_type == 'uimm'

    def is_simm(self):
        return self.operand_type == 'simm' or self.operand_type == 'offset'

    def is_uimm(self):
        return self.operand_type == 'uimm'

    def __repr__(self):
        return "<%s: %s %s>"%(self.name, self.operand_type, self.inst_bit_string)

class RiscvMeta:
    def __init__(self, path, base, extension_letters):
        # path should point to something like path/to/riscv-meta/meta
        meta_files = ['codecs', 'compression', 'constraints', 'csrs', 'enums',
                'extensions', 'formats', 'glossary', 'notation',
                'opcode-descriptions', 'opcode-fullnames',
                'opcode-pseudocode-alt', 'opcode-pseudocode-c', 'opcodes',
                'operands', 'pseudos', 'registers', 'types']
        self.riscv_meta_dir = path
        self.meta = {}
        for f in meta_files:
            self.meta[f] = read_file(os.path.join(self.riscv_meta_dir, f))

        ## TODO: make these inputs for this script
        self.extensions = [base + ext for ext in extension_letters]

        # must parse operands before parsing instructions
        self.operands = self.parse_operands()
        self.insts = self.parse_instructions()

        # reduce known operands
        self.used_operands = {}
        for (inst_name, bsv_val, inst_args, inst_extensions) in self.insts:
            for inst_extension in inst_extensions:
                if inst_extension[0:4] == base:
                    included_inst = True
                    for l in inst_extension[4:]:
                        if l not in extension_letters:
                            included_inst = False
                    if included_inst:
                        for operand in inst_args:
                            self.used_operands[operand] = self.operands[operand]

        print('extensions = ' + str(self.extensions))

    def parse_operands(self):
        operands = {}
        for operand_row in self.meta['operands']:
            new_operand = RiscvOperand(operand_row)
            operands[new_operand.name] = new_operand
        return operands

    def parse_instructions(self):
        opcodes = list(map( lambda x : x[0], self.meta['opcodes'] ))
        codecs = list(map( lambda x : x[0], self.meta['codecs'] ))
        parsed_insts = []

        for instline_orig in self.meta['opcodes']:
            instline = copy.copy(instline_orig)
            # initial values
            inst_args = []
            inst_opcode = []
            inst_extension = []
            inst_mask = 0
            inst_match = 0

            # get inst_name
            inst_name = instline[0]
            if '@' in inst_name:
                # not a real instruction
                continue
            instline.pop(0)

            assert len(instline) > 0, 'unexpected end of instline during parsing'

            while instline[0] not in codecs:
                if instline[0] in self.operands:
                    # known operand
                    inst_args.append(instline[0])
                else:
                    # bit constraint
                    (bits, val) = instline[0].split('=', 1)
                    if val != 'ignore':
                        match = 0
                        mask = 0
                        if '..' in bits:
                            # range of bits
                            (hi, lo) = map(int, bits.split('..', 1))
                            numbits = hi - lo + 1
                            mask = ((1 << numbits) - 1) << lo
                            match = int(val, 0) << lo
                        else:
                            # one bit
                            bindx = int(bits)
                            mask = 1 << bindx
                            match = int(val, 0) << bindx
                        assert mask & match == match, 'value too large for mask in instruction %s' % inst_name
                        assert inst_mask & mask == 0, 'multiple constraints for same bit in instruction %s' % isnt_name
                        inst_mask = inst_mask | mask
                        inst_match = inst_match | match
                instline.pop(0)
                assert len(instline) > 0, 'unexpected end of instline during parsing'

            assert len(instline) > 0, 'unexpected end of instline during parsing'

            # instline[0] == codec
            instline.pop(0)

            # rest of instline is extensions
            inst_extension = instline

            # now finish parsing the line
            bsv_val = bsv_match_mask_val(inst_match, inst_mask, 32)
            # print '%s: %s, args %s, extension %s' % (inst_name, bsv_val, str(inst_args), str(inst_extension))
            parsed_insts.append((inst_name, bsv_val, inst_args, inst_extension))
        return parsed_insts

    def parse_csrs(self):
        csrs = []
        for csrline in self.meta['csrs']:
            csrname = csrline[2]
            # transform csrvalue from 0x105 to 12'h105
            csrvalue = csrline[0].lower()
            assert(csrvalue[0:2] == '0x')
            csrvalue = "12'h" + csrvalue[2:].lower()
            csrs.append( (csrname, csrvalue) )
        return csrs

    def print_bsv_decoder(self, filename):
        decoder = '/* Automatically generated by meta-parse.py */\n'
        decoder = decoder + license
        decoder = decoder + '''
`include "Opcodes.defines"
import RVTypes::*;

typedef struct {
    Maybe#(RegType) rs1;
    Maybe#(RegType) rs2;
    Maybe#(RegType) rs3;
    Maybe#(RegType) dst;
    ImmType imm;
} InstType deriving (Bits, Eq, FShow);

function InstType toInstType(Instruction inst);
    Maybe#(RegType) i = tagged Valid Gpr;
    Maybe#(RegType) f = tagged Valid Fpu;
    Maybe#(RegType) n = tagged Invalid;
    InstType ret = (case (inst) matches
'''

        defined_macros = []
        skipped_macros = []
        for (inst_name, bsv_val, inst_args, inst_extension) in self.insts:
            macro_name = inst_name.replace('.','_').upper()
            (rd, rs1, rs2, rs3, imm) = get_inst_types(inst_args)
            if functools.reduce( lambda x, y: x or y, [x == y for x in inst_extension for y in self.extensions] ):
                decoder = decoder + '            %-16sInstType{rs1: %s, rs2: %s, rs3: %s, dst: %s, imm: %-4s};\n' % ('`' + macro_name + ':',rs1,rs2,rs3,rd,imm)
            else:
                skipped_macros.append(macro_name)
        decoder = decoder + '''            default:        ?;
        endcase);
    if ((ret.dst == tagged Valid Gpr) && (getInstFields(inst).rd == 0)) begin
        ret.dst = tagged Invalid;
    end
    return ret;
endfunction
'''
        with open(filename, 'w') as f:
            f.write(decoder)

    def print_verilog_decoder(self, filename):
        verilog_decoder = '/* Automatically generated by meta-parse.py */\n'
        verilog_decoder = verilog_decoder + license
        verilog_decoder = verilog_decoder + '''
module toInstType_verilog (in, out);
    input [31:0] in;
    output [10:0] out;

    wire [1:0] i;
    wire [1:0] f;
    wire [1:0] n;

    wire [2:0] None;
    wire [2:0] I;
    wire [2:0] S;
    wire [2:0] SB;
    wire [2:0] U;
    wire [2:0] UJ;
    wire [2:0] Z;

    reg [10:0] out_tmp;
    reg [10:0] out;

    // assign n = 2'b0x;
    assign i = 2'b10;
    assign f = 2'b11;

    assign None = 3'b000;
    assign I    = 3'b001;
    assign S    = 3'b010;
    assign SB   = 3'b011;
    assign U    = 3'b100;
    assign UJ   = 3'b101;
    assign Z    = 3'b110;

    always @ (in)
        casez (in)
'''

        for (inst_name, bsv_val, inst_args, inst_extension) in self.insts:
            macro_name = inst_name.replace('.','_').upper()
            (rd, rs1, rs2, rs3, imm) = get_inst_types(inst_args)
            if functools.reduce( lambda x, y: x or y, [x == y for x in inst_extension for y in self.extensions] ):
                # verilog generation
                if rs1 == 'n':
                    rs1 = "2'b0x"
                if rs2 == 'n':
                    rs2 = "2'b0x"
                if rs3 == 'n':
                    rs3 = "2'b0x"
                if rd == 'n':
                    rd = "2'b0x"
                verilog_decoder = verilog_decoder + '            %s: out_tmp = {%s, %s, %s, %s, %s};\n' % (bsv_val,rs1,rs2,rs3,rd,imm)
        verilog_decoder = verilog_decoder + '''            default: out_tmp = 11'bxxxxxxxxxxx;
        endcase

    always @ (in or out_tmp)
        if ((out_tmp[4:3] == 2'b10) && (in[11:7] == 5'b00000))
            out = out_tmp & 11'b11111100111;
        else
            out = out_tmp;

endmodule
'''
        with open(filename, 'w') as f:
            f.write(verilog_decoder)

    def print_macro_definitions(self, filename):
        macro_definitions = '/* Automatically generated by meta-parse.py */\n'
        macro_definitions = macro_definitions + license + '\n'

        defined_macros = []
        skipped_macros = []
        for (inst_name, bsv_val, inst_args, inst_extension) in self.insts:
            macro_name = inst_name.replace('.','_').upper()
            (rd, rs1, rs2, rs3, imm) = get_inst_types(inst_args)
            if functools.reduce( lambda x, y: x or y, [x == y for x in inst_extension for y in self.extensions] ):
                macro_definitions = macro_definitions + '`define %-18s %s\n' % (macro_name, bsv_val)
            else:
                skipped_macros.append(macro_name)

        macro_definitions = macro_definitions + '\n// unused macros\n'
        # finish up macro definitions
        for (inst_name, bsv_val, inst_args, inst_extension) in self.insts:
            macro_name = inst_name.replace('.','_').upper()
            if (macro_name in skipped_macros) and (macro_name not in defined_macros):
                macro_definitions = macro_definitions + '`define %-18s %s\n' % (macro_name, bsv_val)
                defined_macros.append(macro_name)

        with open(filename, 'w') as f:
            f.write(macro_definitions)

    def print_csr_stub(self, filename):
        csrs = self.parse_csrs()
        csrenum = '/* Automatically generated by meta-parse.py */\n'
        csrenum = csrenum + 'typedef enum {\n'
        first = True
        for (csrname, csrvalue) in csrs:
            if not first:
                csrenum = csrenum + ',\n'
            else:
                first = False
            csrenum = csrenum + '    CSR%-16s = %s' % (csrname, csrvalue)
        csrenum = csrenum + '\n} CSR deriving (Bits, Eq, FShow);\n'
        csrenum = csrenum + '\n'
        csrenum = csrenum + 'function Bool isValidCSR(CSR csr);\n'
        csrenum = csrenum + '    return (case (csr)\n'
        for (csrname, csrvalue) in csrs:
            csrenum = csrenum + '            CSR%-20s True;\n' % (csrname + ':')
        csrenum = csrenum + '            default:                False;\n'
        csrenum = csrenum + '        endcase);\n'
        csrenum = csrenum + 'endfunction'
        csrenum = csrenum + '\n'
        csrenum = csrenum + 'function Reg#(Data) getCSR(CSR csr);\n'
        csrenum = csrenum + '    return (case (csr)\n'
        for (csrname, csrvalue) in csrs:
            csrenum = csrenum + '            CSR%-20s %s;\n' % (csrname + ':', csrname + '_csr')
        csrenum = csrenum + '            default:                ?;\n'
        csrenum = csrenum + '        endcase);\n'
        csrenum = csrenum + 'endfunction'
        with open(filename, 'w') as f:
            f.write(csrenum)

    def print_imm_stub(self, filename):
        # Find unique encodings
        imm_encodings = {}
        for operand in self.used_operands:
            if self.operands[operand].is_imm():
                if self.operands[operand].inst_bit_string in imm_encodings:
                    imm_encodings[self.operands[operand].inst_bit_string] += [operand]
                else:
                    imm_encodings[self.operands[operand].inst_bit_string] = [operand]

        keys = list(imm_encodings.keys())
        keys.sort(key = lambda x: x[::-1])
        for x in keys:
            print("%-24s %s" % (str(imm_encodings[x]), x))

        # Immediate type enumeration
        imm_stub = 'typedef enum {\n'
        imm_stub += '    IMM_NONE'
        for operand in self.used_operands:
            if self.operands[operand].is_imm():
                imm_stub += ',\n    IMM_%s' % operand.upper()
        imm_stub += '\n} ImmType deriving (Bits, Eq, FShow);\n\n'

        # Immediate decoding function
        imm_stub += 'function Maybe#(Data) getImm(Bit#(32) inst, ImmType immType);\n'
        imm_stub += '    return (case (immType)\n'
        for operand in self.used_operands:
            if self.operands[operand].is_imm():
                imm_stub += '            IMM_%s: tagged Valid %s;\n' % (operand.upper(), self.operands[operand].inst_bit_string)
        imm_stub += '            default: tagged Invalid;\n'
        imm_stub += '        endcase);\n'
        imm_stub += 'endfunction\n'
        with open(filename, 'w') as f:
            f.write(imm_stub)


if __name__ == '__main__':
    riscv_meta_dir = '../riscv-meta/meta/'
    ## TODO: make these inputs for this script
    base = 'rv64'
    extension_letters = 'imafds'

    rvmeta = RiscvMeta(riscv_meta_dir, base, extension_letters)

    rvmeta.print_bsv_decoder('Opcodes.bsv')
    rvmeta.print_verilog_decoder('toInstType_verilog.v')
    rvmeta.print_macro_definitions('Opcodes.defines')
    rvmeta.print_csr_stub('CSRs.stub.bsv')
    rvmeta.print_imm_stub('Imm.stub.bsv')

