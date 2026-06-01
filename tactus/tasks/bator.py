"""Bator task — ODB subbase creation via the BATOR binary.

Runs BATOR for a single observation type (given by the *OBSTYPE* ecFlow
variable) to produce an ``ECMA.<obstype>`` ODB subbase.

"""
import json

from ..config_parser import ConfigPaths
from ..datetime_utils import as_datetime
from ..logs import logger
from ..namelist import NamelistGenerator
from ..odbtools import Bator as OdbBator
from ..geo_utils import LambertDomainFromConfig

from .base import Task
from .batch import BatchJob


class Bator(Task):
    """Run BATOR for one observation type to produce an ECMA ODB subbase."""

    def __init__(self, config):
        """Construct Bator task.

        Args:
            config (tactus.ParsedConfig): Experiment configuration.
        """
        Task.__init__(self, config, __class__.__name__)
        self.basetime = as_datetime(config["general.times.basetime"])

        obstype = config["task.args.obstype"]
        obs_provider = config.get("da.obs_provider", "UWC")
        self._provider = config.get("da.providers", {}).get(obs_provider, {})
        self.bator = OdbBator(
            obstype,
            self.wdir,
            f"ECMA.{obstype}",
            self.basetime,
            config.get("da.nbpool", 12),
            window_len=config.get("da.bator_window_len", 180),
            window_shift=config.get("da.bator_window_shift", -90),
            slot_len=config.get("da.bator_slot_len", 0),
            center_len=config.get("da.bator_center_len", 0),
            nbslot=config.get("da.bator_nbslot", 1),
            lamflag=True,
        )
        self.nlgen = NamelistGenerator(config, "bator")
        # Move to general Task
        self.domain = LambertDomainFromConfig(config)

        logger.debug("Constructed Bator task for obstype={}", obstype)

    def execute(self):
        """Run BATOR for the configured obstype.

        Inputs are read from the ObsPrep scratch directory.
        Output ``ECMA.<obstype>`` is archived to the Bator scratch directory.
        """

        # --- namelists and constants ---
        self.nlgen.generate_namelist("bator", "NAMELIST")
        self.nlgen.generate_namelist("bator", "bator_gpssol")
        self.nlgen.generate_namelist("bator", "bator_rgb")

        # lamflag
        if self.bator.lamflag:
            self.nlgen.generate_namelist("bator_lamflag",
                                         f"aldnml_lamflag_{self.domain.name}")

        # --- static input files ---
        input_definition = ConfigPaths.path_from_subpath(
            self.platform.get_system_value("bator_input_definition")
        )
        with open(input_definition, "r", encoding="utf-8") as f:
            input_data = json.load(f)
        self.fmanager.input_data_iterator(input_data)

        # --- stage obs file(s) from ObsPrep output ---
        local_name = self.bator.stage_obs()

        if not local_name:
            logger.info(
                "Bator: no obs file for obstype '{}' — skipping BATOR run.",
                self.bator.obstype,
            )
            return

        # --- create refdata and batormap ---
        self.bator.write_refdata_and_batormap(local_name)

        script = self.get_binary("create_ioassign")
        binary = self.get_binary("IOASSIGN")
        self.bator.create_ioassign(script, binary)

        # --- run BATOR ---
        # The platform wrapper (srun) acts as the MPI launcher on SLURM systems;
        # adding a separate mpirun prefix causes double-MPI-init and DR_HOOK abort.

        binary = self.get_binary("BATOR")
        BatchJob(self.bator.rte, wrapper=self.wrapper)
        self.bator.run(binary)

        self.bator.archive()
