import pyaf.Bench.TS_datasets as tsds
import pyaf.tests.artificial.process_artificial_dataset as art




dataset = tsds.generate_random_TS(N = 128 , FREQ = 'D', seed = 0, trendtype = "constant", cycle_length = 7, transform = "log", sigma = 0.0, exog_count = 100, ar_order = 12);

art.process_dataset(dataset);