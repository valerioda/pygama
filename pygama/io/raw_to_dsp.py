#!/usr/bin/env python3
import sys, json, os
import numpy as np
import argparse
import importlib

from pygama.dsp.ProcessingChain import ProcessingChain
# import pygama.dsp.processors
from pygama.dsp.units import *
from pygama.io import lh5


def main():
    """
    Below is commented out example of using raw_to_dsp function
    """

    # json_file = "raw_to_dsp.json"
    # filename = os.path.expandvars("/Volumes/LaCie/Data/CAGE/pygama_raw/raw_run11.lh5")
    # groupname = "/ORSIS3302DecoderForEnergy"
    #
    #
    # with open(json_file) as f:
    #     config = json.load(f)
    # paths = config["paths"]
    # options = config["options"]
    # processor_outputs = []
    # for output in config["processors"]:
    #     processor_outputs.append(output)
    #
    # lh5_in = lh5.Store()
    # file = os.path.expandvars(paths["tier1_dir"] + "/" + filename)
    # groupname = paths["t1_group_name"]
    # lh5_data = lh5_in.read_object(groupname, file)
    #
    # lh5_out, proc = raw_to_dsp(lh5_data, json_file)


def raw_to_dsp(lh5_in, json_file, buffer_len=8):
    """
    Will add doc string when I have time
    """

    with open(json_file) as f:
        config = json.load(f)
    paths = config["paths"]
    options = config["options"]

    wf_in = lh5_in["waveform"]["values"].nda
    dt = lh5_in['waveform']['dt'].nda[0] * unit_parser.parse_unit(lh5_in['waveform']['dt'].attrs['units'])


    proc = ProcessingChain(block_width=buffer_len, clock_unit=dt, verbosity=3) #NOTE Need to add verbosity input to function
    proc.add_input_buffer("wf", wf_in, dtype='float32')
    proc.set_processor_list(json_file)
    # proc.get_column_names() loop over

    lh5_out = lh5.Table(size=proc._buffer_len)

    for output in config["outputs"]:

        lh5_out.add_field(output, lh5.Array(proc.get_output_buffer(output),
                                               attrs={"units":"ADC"}))

    return lh5_out, proc





def example():

    lh5_in = lh5.Store()
    #data = lh5_in.read_object(args.group, args.file, 0, args.chunk)
    data = lh5_in.read_object(args.group, args.file)

    wf_in = data['waveform']['values'].nda
    dt = data['waveform']['dt'].nda[0] * unit_parser.parse_unit(data['waveform']['dt'].attrs['units'])

    # Set up processing chain
    proc = ProcessingChain(block_width=args.block, clock_unit=dt, verbosity=args.verbose)
    proc.add_input_buffer("wf", wf_in, dtype='float32')

    # Basic Filters
    proc.add_processor(mean_stdev, "wf[0:1000]", "bl", "bl_sig")
    proc.add_processor(np.subtract, "wf", "bl", "wf_blsub")
    proc.add_processor(pole_zero, "wf_blsub", 70*us, "wf_pz")
    proc.add_processor(trap_norm, "wf_pz", 10*us, 5*us, "wf_trap")
    proc.add_processor(asymTrapFilter, "wf_pz", 0.05*us, 2*us, 4*us, "wf_atrap")

    # Timepoint calculation
    proc.add_processor(np.argmax, "wf_blsub", 1, "t_max", signature='(n),()->()', types=['fi->i'])
    proc.add_processor(time_point_frac, "wf_blsub", 0.95, "t_max", "tp_95")
    proc.add_processor(time_point_frac, "wf_blsub", 0.8, "t_max", "tp_80")
    proc.add_processor(time_point_frac, "wf_blsub", 0.5, "t_max", "tp_50")
    proc.add_processor(time_point_frac, "wf_blsub", 0.2, "t_max", "tp_20")
    proc.add_processor(time_point_frac, "wf_blsub", 0.05, "t_max", "tp_05")
    proc.add_processor(time_point_thresh, "wf_atrap[0:1200]", 0, "tp_0")

    # Energy calculation
    proc.add_processor(np.amax, "wf_trap", 1, "trapEmax", signature='(n),()->()', types=['fi->f'])
    proc.add_processor(fixed_time_pickoff, "wf_trap", "tp_0", 5*us+9*us, "trapEftp")
    proc.add_processor(trap_pickoff, "wf_pz", 1.5*us, 0, "tp_0", "ct_corr")

    # Current calculation
    proc.add_processor(avg_current, "wf_pz", 10, "curr")
    proc.add_processor(np.amax, "curr", 1, "curr_amp", signature='(n),()->()', types=['fi->f'])
    proc.add_processor(np.divide, "curr_amp", "trapEftp", "aoe")

    # Set up the LH5 output
    lh5_out = lh5.Table(size=proc._buffer_len)
    lh5_out.add_field("trapEmax", lh5.Array(proc.get_output_buffer("trapEmax"), attrs={"units":"ADC"}))
    lh5_out.add_field("trapEftp", lh5.Array(proc.get_output_buffer("trapEftp"), attrs={"units":"ADC"}))
    lh5_out.add_field("ct_corr", lh5.Array(proc.get_output_buffer("ct_corr"), attrs={"units":"ADC*ns"}))
    lh5_out.add_field("bl", lh5.Array(proc.get_output_buffer("bl"), attrs={"units":"ADC"}))
    lh5_out.add_field("bl_sig", lh5.Array(proc.get_output_buffer("bl_sig"), attrs={"units":"ADC"}))
    lh5_out.add_field("A", lh5.Array(proc.get_output_buffer("curr_amp"), attrs={"units":"ADC"}))
    lh5_out.add_field("AoE", lh5.Array(proc.get_output_buffer("aoe"), attrs={"units":"ADC"}))

    lh5_out.add_field("tp_max", lh5.Array(proc.get_output_buffer("tp_95"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_95", lh5.Array(proc.get_output_buffer("tp_95"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_80", lh5.Array(proc.get_output_buffer("tp_80"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_50", lh5.Array(proc.get_output_buffer("tp_50"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_20", lh5.Array(proc.get_output_buffer("tp_20"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_05", lh5.Array(proc.get_output_buffer("tp_05"), attrs={"units":"ticks"}))
    lh5_out.add_field("tp_0", lh5.Array(proc.get_output_buffer("tp_0"), attrs={"units":"ticks"}))

    print("Processing:\n",proc)
    proc.execute()

    out = args.output
    if out is None:
        out = 't2_'+args.file[args.file.rfind('/')+1:].replace('t1_', '')
    print("Writing to: "+out)
    lh5_in.write_object(lh5_out, "data", out)

if __name__=="__main__":
    main()
