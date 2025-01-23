#!/usr/bin/python3
# -*- coding: ascii -*-
########################################################################
# cyusb-fw-extract.py - Extract firmware from Cypress USB script files 
# Copyright (C) 2008  Dwayne C. Litzenberger <dlitz@dlitz.net>
# Copyright (C) 2025  Fritz Webering <fritz@webering.eu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
########################################################################
#
# This program attempts to create fxload-compatible firmware images by
# analyzing a supplied Cypress USB script file.  Cypress USB script files
# typically have the ".spt" file extension, and are used in devices that
# incorporate the Cypress Semiconductor EZ-USB (CY7C68xxx) series
# microcontrollers.  These script files are executed on Windows by the Cypress
# Generic USB Driver (CyUsb.sys).
#
# Version 0.2 (2025-01-23):
# - Ported from Python 2.7 to Python 3
#
# Version 0.1:
# - Original python 2 script by Dwayne C. Litzenberger
# - Source: https://ftp.dlitz.net/pub/dlitz/cyusb-fw-extract/0.1/cyusb-fw-extract.py
#
# This program is known to work for the following firmware(s):
#   - ADS Tech Instant Video-To-Go RDX-160 (hardware H.264 encoder)
#       + "vtogold.spt" on the CD "Instant Video To-Go CD, Ver. 1.2"
#   - Lecroy LogicStudio 16 (USB Logic Analyzer)
#     (see also: https://sigrok.org/wiki/LeCroy_LogicStudio)
#       + "LogicStudio16Load.spt" from the LogicStudio_install_x86.msi
#         inside logicstudio_32_v1.2.5.0.zip from the LeCroy Website
#         https://www.teledynelecroy.com/support/softwaredownload/logicstudio.aspx
#

import sys
import os.path
import struct
import getopt

PROGRAM_VERSION = "cyusb-fw-extract 0.2"

def exit_usage():
    print("""Usage: %s [-v] -oPREFIX SPTFILE

Read SPTFILE and output PREFIX_1.ihx, PREFIX_2.ihx...
Use -v for verbose output.
""" % (sys.argv[0],), file=sys.stderr)
    sys.exit(2)

class CSPTChunk(object):
    @classmethod
    def fromfile(cls, file):
        chunk = file.read(4)
        if not chunk:
            return None     # EOF
        if chunk[:4] != b"CSPT":
            raise ValueError("Error reading chunk: expected 'CSPT', got %r" % (chunk[:4],))
        chunk += file.read(4)
        (length,) = struct.unpack("<L", chunk[4:8])
        if length < 8:
            raise ValueError("Error reading chunk: chunk length %d too small" % (length,))
        chunk += file.read(length - 8)
        if len(chunk) < length:
            raise EOFError("Error reading chunk: file truncated")

        fmt = "<LLLLBBHLLL"
        hdr_len = struct.calcsize(fmt)
        (magic,         # 0:  Long word
         length,        # 4:  Long word
         dummy8,        # 8:  Long word
         dummy12,       # 12: Long word
         request,       # 16: Byte
         dummy17,       # 17: Byte
         addr,          # 18: Half word
         dummy20,       # 20: long word
         dummy24,       # 24: long word
         data_len,      # 28: long word
        ) = struct.unpack(fmt, chunk[:hdr_len])
        data = chunk[hdr_len:]
        if len(data) != data_len:
            raise ValueError("Error reading chunk: data length mismatch (%d vs %d)" % (len(data), data_len))

        if len(data) < data_len:
            raise EOFError("Error reading chunk: file truncated")
        
        obj = cls()
        obj.raw_chunk = chunk
        obj.dummies = (dummy8, dummy12, dummy17, dummy20, dummy24)
        obj.request = request
        obj.address = addr
        obj.data = data

        return obj

    def __repr__(self):
        return """<%s request=0x%02x address=0x%04x length=%d dummies=%r>""" % (
            self.__class__.__name__, self.request, self.address,
            len(self.data), self.dummies)

def make_ihx_data_lines(addr, data, width=16):
    """Generate a list of Intel Hex format lines"""
    if not 1 <= width < 256:
        raise ValueError("width must be in range(1,256)")
    if not 0 <= addr <= 0xffff or not 0 <= addr + len(data) - 1 <= 0xffff:
        raise NotImplementedError("Addresses greater than 16 bits not supported")
    for i in range(0, len(data), width):
        a = addr + i
        d = data[i:i+width]
        assert 0 <= a <= 0xffff
        assert 0 <= a+width-1 <= 0xffff
        octets = []
        octets.append(len(d))   # Load record length
        octets.append(a >> 8)   # high address bits
        octets.append(a & 0xff) # low address bits
        octets.append(0x00)        # record type = 00 (data record)
        octets += list(d)

        # checksum
        checksum = 0
        for c in octets:
            checksum = (checksum + c) & 0xff
        checksum = (0x100 - checksum) & 0xff
        octets.append(checksum)

        line = ":%s\n" % (bytes(octets).hex().upper(),)
        yield line

def main():
    # Parse arguments
    verbose = False
    output_prefix = None

    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'vo:')
    except getopt.GetoptError as exc:
        print("error: %s" % (str(exc),), file=sys.stderr)
        exit_usage()

    if len(args) != 1:
        print("error: this program takes exactly one argument", file=sys.stderr)
        exit_usage()
    (input_path,) = args
    
    for (opt, optarg) in optlist:
        if opt == '-v':
            verbose = True
        elif opt == "-o":
            output_prefix = optarg
        else:
            assert 0    # This should never happen

    if output_prefix is None:
        print("error: no output prefix specified", file=sys.stderr)
        exit_usage()

    warning_count = 0
    cpucs_address = None    # Address of the CPUCS register
    cpu_reset = 0           # Value of the 8051RES bit (1 = CPU in RESET)
    stage_number = 0
    input_file = open(input_path, "rb")
    chunk = CSPTChunk.fromfile(input_file)
    output_file = None
    while chunk is not None:
#        if verbose:
#            print repr(chunk)

        if chunk.request != 0xa0:
            print("warning: skipping unrecognized device request 0x%02x" % (chunk.request,), file=sys.stderr)
            warning_count += 1
            continue

        # FIXME: What do these bits mean?  Do they need to be set this way?
        if chunk.dummies != (0x20, 0x40000000, 0x75, 0x900000, 0xf):
            print("warning: file format not entirely understood: %r" % (chunk.dummies,), file=sys.stderr)
            #print("                  ...instead of the expected: %r" % ((0x20, 0x40000000, 0x75, 0x900000, 0xf), ), file=sys.stderr)
            warning_count += 1

        # The first request in the input file should be to write a single byte
        # to the CPUCS register.  Prior to uploading the firmware, the 8051 CPU
        # core must be put into a RESET state by setting CPUCS.0 = 1.  When the
        # upload is complete, the 8051 core must be restarted by setting
        # CPUCS.0 = 0.  This process is done once for a single-stage loader, or
        # twice for a two-stage loader.

        if cpucs_address is None:   # First write
            if len(chunk.data) != 1:
                print("warning: skipping multi-byte write past CPUCS" % (chunk.request,), file=sys.stderr)
                warning_count += 1
                continue
            
            if not chunk.data[0] & 1:      # The reset bit should be
                print("warning: first write clears CPUCS.0 instead of setting it" % (chunk.request,), file=sys.stderr)
                warning_count += 1

            cpucs_address = chunk.address
            if verbose:
                print("Detected CPUCS address: 0x%04x" % (cpucs_address,))
        
        if chunk.address == cpucs_address:
            if len(chunk.data) != 1:
                print("warning: skipping multi-byte write past CPUCS" % (chunk.request,), file=sys.stderr)
                warning_count += 1
                continue
            
            new_reset_bit = chunk.data[0] & 1      # 8051RES = CPUCS.0
            if new_reset_bit == cpu_reset:
                print("warning: skipping write to CPUCS that doesn't change CPUCS.0" % (chunk.request,), file=sys.stderr)
                warning_count += 1
                continue
            
            if not cpu_reset:
                # Open a new file
                stage_number += 1
                filename = output_prefix + "_%d.ihx" % (stage_number,)
                if verbose:
                    print("Writing stage %d to %s" % (stage_number, filename,))
                output_file = open(filename, "w")
                output_file.write("# Extracted using %s\n" % (PROGRAM_VERSION,)) 
                output_file.write("# Stage %d from %s\n" % (stage_number, os.path.basename(input_path).replace("\n", " ")))
            else:
                # Write the end-of-file marker and close current file
                output_file.write(":00000001FF\n")
                output_file.close()
                output_file = None

            cpu_reset = new_reset_bit
        
        else:

            for line in make_ihx_data_lines(chunk.address, chunk.data):
                output_file.write(line)

        chunk = CSPTChunk.fromfile(input_file)

    if cpu_reset:
        print("warning: input file finished without clearing CPUCS.0", file=sys.stderr)
        warning_count += 1

    input_file.close()
    
    if warning_count > 0:
        print("Finished with %d warnings." % (warning_count,), file=sys.stderr)
        sys.exit(1)
    else:
        if verbose:
            print("Finished with no warnings.")
        sys.exit(0)

if __name__ == '__main__':
    main()


# vim:set ts=4 sw=4 sts=4 expandtab:
