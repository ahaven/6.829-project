from __future__ import division
import collections
import math

BitRate = collections.namedtuple("BitRate", ["phy", "kbps", "user_kbps",
                                             "code", "dot11_rate"])

RATES = [
    BitRate("cck", 1000, 900, 0, 2),
    BitRate("cck", 2000, 1900, 1, 4),
    BitRate("cck", 5500, 4900, 2, 11),
    BitRate("cck", 11000, 8100, 3, 22),
    BitRate("ofdm", 6000, 5400, 4, 12),
    BitRate("ofdm", 9000, 7800, 5, 18),
    BitRate("ofdm", 12000, 10100, 6, 24),
    BitRate("ofdm", 18000, 14100, 7, 36),
    BitRate("ofdm", 24000, 17700, 8, 48),
    BitRate("ofdm", 36000, 23700, 9, 72),
    BitRate("ofdm", 48000, 27400, 10, 96),
    BitRate("ofdm", 54000, 30900, 11, 108),

    # Ignored but here for completeness
    BitRate("ht_ss", 6500, 6400, 0, 0),
    BitRate("ht_ss", 13000, 12700, 1, 1),
    BitRate("ht_ss", 19500, 18800, 2, 2),
    BitRate("ht_ss", 26000, 25000, 3, 3),
    BitRate("ht_ss", 39000, 36700, 4, 4),
    BitRate("ht_ss", 52000, 48100, 5, 5),
    BitRate("ht_ss", 58500, 53500, 6, 6),
    BitRate("ht_ss", 65000, 59000, 7, 7),
    BitRate("ht_hgi", 72200, 65400, 7, 7),
    BitRate("ht_ds", 13000, 12700, 8, 8),
    BitRate("ht_ds", 26000, 24800, 9, 9),
    BitRate("ht_ds", 39000, 36600, 10, 10),
]

def ieee80211_to_idx(mbps):
    opts = [i for i, rate in enumerate(RATES)
            if rate.dot11_rate == int(round(2 * mbps))]
    if opts:
        return opts[0]
    else:
        raise ValueError("No bitrate with throughput {} Mbps exists".format(mbps))


class EWMA:
    def __init__(self, time, time_step, pval):
        self.p = pval
        self.time = time
        self.step = time_step
        self.val = None

    def feed(self, time, val):
        if self.val is None:
            newval = val
        else:
            p = self.p
            newval = self.val * p + val * (1 - p)

        self.val = int(newval)
        self.time = time

    def read(self):
        if self.val is not None:
            return self.val
        else: 
            return None

class BalancedEWMA:
    def __init__(self, time, time_step, pval):
        self.p = pval
        self.time = time
        self.step = time_step

        self.blocks = 0
        self.denom = 0
        self.val = None

    def feed(self, time, num, denom):
        if self.blocks == 0:
            self.denom = denom
            newval = num / denom
        else:
            avg_block = self.denom / self.blocks
            block_weight = denom / avg_block
            relweight = self.p / (1 - self.p)

            prob = num / denom

            newval = (self.val * relweight + prob * block_weight) / \
                     (relweight + block_weight)

        self.blocks += 1
        self.val = newval
        self.time = time

    def read(self):
        if self.val:
            return int(self.val * 18000)
        else:
            return None

def tx_time(rix, length=1200): #rix is index to RATES, length in bytes
    mbps = RATES[rix].dot11_rate / 2000

    if RATES[rix].phy == "ofdm":
        '''* OFDM:
        *
        * N_DBPS = DATARATE x 4
        * N_SYM = Ceiling((16+8xLENGTH+6) / N_DBPS)
        *	(16 = SIGNAL time, 6 = tail bits)
        * TXTIME = T_PREAMBLE + T_SIGNAL + T_SYM x N_SYM + Signal Ext
        *
        * T_SYM = 4 usec
        * 802.11a - 17.5.2: aSIFSTime = 16 usec
        * 802.11g - 19.8.4: aSIFSTime = 10 usec +
        *	signal ext = 6 usec
        */'''
        dur = 16 # SIFS + signal ext */
        dur += 16 # 17.3.2.3: T_PREAMBLE = 16 usec */
        dur += 4 # 17.3.2.3: T_SIGNAL = 4 usec */
        dur += 4 * (round((16+8*(length+4)+6)/(4*mbps))+1) # T_SYM x N_SYM

    else:
        '''
        * 802.11b or 802.11g with 802.11b compatibility:
        * 18.3.4: TXTIME = PreambleLength + PLCPHeaderTime +
        * Ceiling(((LENGTH+PBCC)x8)/DATARATE). PBCC=0.
        *
        * 802.11 (DS): 15.3.3, 802.11b: 18.3.4
        * aSIFSTime = 10 usec
        * aPreambleLength = 144 usec or 72 usec with short preamble
        * aPLCPHeaderLength = 48 usec or 24 usec with short preamble
        *'''
        dur = 10 # aSIFSTime = 10 usec
        dur += (72 + 24) #using short preamble, otw we'd use (144 + 48)
        dur += round((8*(length + 4))/mbps)+1
    
    return dur
