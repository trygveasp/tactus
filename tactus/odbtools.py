


import os
import subprocess
from collections.abc import Mapping
from .logs import logger
from .os_utils import tactusmakedirs


arch_env = {
    'F_RECLUNIT': 'BYTE',
    'F_UFMTENDIAN': 'big',
    # "F_UFMTENDIAN": "big:10,33,50,54,81",
}

task_env = {
    'TO_ODB_ECMWF': '0',
    'EC_MEMINFO': '0',
    'EC_LINUX_TRBK': '1',
    'EC_MPI_ATEXIT': '0',
    'OMP_NUM_THREADS': '1',
    'MKL_DYNAMIC': 'FALSE',
    'DR_HOOK': '0',
    'DR_HOOK_SILENT': '1',
    'DR_HOOK_IGNORE_SIGNALS': '-1',
}


class Odb1():

    def __init__(self, wdir,
                 odb_base,
                 basetime,
                 npools,
                 odb_io_method=4,
                 filesize=128,
                 bator_window_len=180,
                 bator_window_shift=-90,
                 bator_slot_len=0,
                 bator_center_len=0,
                 bator_nbslot=1,
                 merge_odb_direct=0,
                 obstype=None):

        odb_env = {
            'TO_ODB_ECMWF': '0',
            'TO_ODB_SWAPOUT': '0',
            'ODB_DEBUG': '0',
            'ODB_CTX_DEBUG': '0',
            'ODB_REPRODUCIBLE_SEQNO': '2',
            'ODB_STATIC_LINKING': '1',
            'ODB_ECMA_CREATE_POOLMASK': '1',
            'ODB_TRACE_FILE': 'List_odb',
            'TO_ODB_DEBUG': '0',
            'ODB_TRACE_PROC': '0',
            'ODB_CCMA_CREATE_DIRECT': '1',
            'ODB_CCMA_CREATE_POOLMASK': '1',
        }
        rte = arch_env.copy()
        rte.update(odb_env)
        rte.update(task_env)
        rte.update({
            'BATOR_WINDOW_LEN': str(bator_window_len),
            'BATOR_WINDOW_SHIFT': str(bator_window_shift),
            'BATOR_SLOT_LEN': str(bator_slot_len),
            'BATOR_CENTER_LEN': str(bator_center_len),
            'BATOR_NBSLOT': str(bator_nbslot),
            'ODB_SRCPATH_ECMA': f"{wdir}/ECMA",
            'ODB_DATAPATH_ECMA': f"{wdir}/ECMA",
            'ODB_SRCPATH_CCMA': f"{wdir}/CCMA",
            'ODB_DATAPATH_CCMA': f"{wdir}/CCMA",
            'ODB_ECMA_POOLMASK_FILE': f"{wdir}/ECMA/ECMA.poolmask",
            'ODB_CCMA_POOLMASK_FILE': f"{wdir}/CCMA/CCMA.poolmask",
            'ODB_SRCPATH_RSTBIAS': f"{wdir}/{odb_base}",
            'SWAPP_ODB_IOASSIGN': f"{wdir}/{odb_base}/IOASSIGN",
            'ODB_IO_METHOD': f"{odb_io_method}",
            'ODB_IO_FILESIZE': f"{filesize}",
            'ODB_IO_GRPSIZE': f"{npools}",

            'ODB_ANALYSIS_DATE': f"{basetime.strftime('%Y%m%d')}",
            'ODB_ANALYSIS_TIME': f"{basetime.strftime('%H%M%S')}",
            'TIME_INIT_YYYYMMDD': f"{basetime.strftime('%Y%m%d')}",
            'TIME_INIT_HHMMSS': f"{basetime.strftime('%H%M%S')}",
            'ODB_CMA': f"{odb_base}",
            'ODB_MERGEODB_DIRECT': f"{merge_odb_direct}",
        })
        self.rte = rte
        self.base = "ECMA"
        self.npools = npools
        self.obstype = obstype
        self.basetime = basetime

    def create_ioassign(self, script, binary):
        # --- create ECMA output directory ---
        os.makedirs(f"ECMA.{self.bator.obstype}", exist_ok=True)

        # --- create IOASSIGN file ---
        # create_ioassign internally calls the `ioassign` binary so `.` must be on PATH.

        ioassign_path = os.path.dirname(binary)
        ioassign_env = self.bator.rte.copy()
        ioassign_env["PATH"] = f"{ioassign_path}{os.pathsep}{ioassign_env.get('PATH', '')}"
        result = subprocess.run(
            f"{script} -l{self.bator.base} -n{self.nbpool}",
            shell=True,
            env=ioassign_env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"create_ioassign failed with return code {result.returncode}"
            )
        ioassign_file = os.path.join(self.wdir, "IOASSIGN")
        if not os.path.isfile(ioassign_file):
            raise RuntimeError(
                f"create_ioassign returned 0 but IOASSIGN file not found at {ioassign_file}"
            )
        logger.info("Bator: IOASSIGN created at {}", ioassign_file)

    def run(self, batch, binary):
        batch.rte.update({
            "ODB_FEBINPATH": f"{binary}"
        })
        batch.run(binary)


class Bator(Odb1):

    def __init__(self,
                 obstype,
                 wdir,
                 odb_base,
                 basetime,
                 npools,
                 window_len=180,
                 window_shift=-90,
                 slot_len=0,
                 center_len=0,
                 nbslot=1,
                 lamflag=True):

        self.obstype = obstype
        self.lamflag = lamflag
        Odb1.__init__(self, wdir, odb_base, basetime, npools, bator_window_len=window_len,
                      bator_window_shift=window_shift,
                      bator_slot_len=slot_len,
                      bator_nbslot=nbslot,
                      bator_center_len=center_len)

    def execute(self, batch, binary, wrapper=""):

        Odb1.execute(self, batch, binary, wrapper=wrapper)

    def stage_obs(self):
        """Link the obs file produced by ObsPrep into the work dir.

        Returns the local_name string on success, None if no file is available.
        """
        obsprep_dir = os.path.join(self.wrk, "obsprep")
        spec = self._provider.get(self.obstype)
        if not isinstance(spec, Mapping):
            logger.info(
                "Bator: no provider entry for obstype '{}' — skipping.",
                self.obstype,
            )
            return None

        local_name = spec.get("local_name", self.obstype)
        src = os.path.join(obsprep_dir, local_name)
        if not os.path.isfile(src):
            logger.info(
                "Bator: no obs file '{}' in obsprep dir for obstype '{}' — skipping.",
                local_name,
                self.obstype,
            )
            return None

        if not os.path.lexists(local_name):
            if local_name.startswith("OBSOUL."):
                self._copy_obsoul_fixed_header(src, local_name)
            else:
                os.symlink(src, local_name)
        logger.debug("Bator: staged {} -> {}", src, local_name)
        return local_name

    def copy_obsoul_fixed_header(self, src, local_name):
        """Copy OBSOUL file rewriting the header time to 6-digit HHMMSS format.

        BATOR requires the header line to be "    YYYYMMDD<TAB>HHMMSS".
        Some providers write only a 2-digit HH (e.g. "    20250209          00")
        which causes BATOR to abort with "OBsoul incorrect".
        """
        hhmmss = self.basetime.strftime("%H") + "0000"
        yyyymmdd = self.basetime.strftime("%Y%m%d")
        correct_header = f"    {yyyymmdd}\t{hhmmss}\n"
        with open(src) as fin, open(local_name, "w") as fout:
            fin.readline()  # discard original header
            fout.write(correct_header)
            for line in fin:
                fout.write(line)
        logger.debug("Bator: copied {} with fixed OBSOUL header", local_name)

    def write_refdata_and_batormap(self, local_name):
        """Write refdata and batormap files.

        Format is derived from the local_name prefix (e.g. "OBSOUL.synop" → "OBSOUL").
        """
        yyyy = self.basetime.strftime("%Y")
        mm = self.basetime.strftime("%m")
        dd = self.basetime.strftime("%d")
        rr = self.basetime.strftime("%H")
        fmt = local_name.split(".")[0].upper() if "." in local_name else ""
        if not fmt:
            logger.warning(
                "Bator: cannot derive format from local_name '{}' — skipping refdata/batormap",
                local_name,
            )
            return

        bator_name = self.obstype
        with open("refdata", "w") as fh:
            fh.write(
                f"{self.obstype:<8} {fmt:<8} {bator_name:<16} {yyyy}{mm}{dd} {rr}\n"
            )
        with open("batormap", "w") as fh:
            fh.write(
                f"{self.obstype:<8} {self.obstype:<8} {fmt:<8} {bator_name}\n"
            )

    def run(self, batch, binary):

        Odb1.run(self, batch, binary)

        # --- verify output ---
        ecma_out = f"ECMA.{self.obstype}"
        if not os.path.isdir(ecma_out):
            logger.warning(
                "Bator did not produce {} — marking as complete with warning.",
                ecma_out,
            )

    def archive(self):
        # --- archive output ---

        # TODO archive path
        #out_dir = os.path.join(
        #    self.da_scratch, yyyy, mm, dd, rr, "bator", self.bator.obstype
        #)
        #tactusmakedirs(out_dir)
        #if os.path.isdir(ecma_out):
        #    dst = os.path.join(out_dir, ecma_out)
        #    if os.path.exists(dst):
        #        shutil.rmtree(dst, ignore_errors=True)
        #    shutil.copytree(ecma_out, dst, symlinks=True)
        #     logger.info("Bator: archived {} to {}", ecma_out, out_dir)
