# Copyright (C) 2016 Antoine Carme <Antoine.Carme@Laposte.net>
# All rights reserved.

# This file is part of the Python Automatic Forecasting (PyAF) library and is made available under
# the terms of the 3 Clause BSD license

import pandas as pd
import numpy as np

import pyaf.ForecastEngine as autof
from  pyaf.CodeGen import TS_CodeGenerator as tscodegen
import pyaf.Bench.TS_datasets as tsds

import sys,os
# for timing
import time

import multiprocessing as mp
import threading
from multiprocessing.dummy import Pool as ThreadPool



def createDirIfNeeded(dirname):
    try:
        os.mkdir(dirname);
    except:
        pass

class cBenchmarkError(Exception):
    def __init__(self, msg):
        super().__init__(msg);
        pass

def set_pyaf_logger(log_filename):
    import logging
    import logging.config
    pyaf_logger = logging.getLogger('pyaf.std')
    pyaf_logger.setLevel(logging.DEBUG)
    # handler = logging.FileHandler(log_filename)    
    # pyaf_logger.addHandler(handler)
    pass

def run_bench_process(a):
    print("STARTING_BENCH_FOR_SIGNAL" , a.mBenchName, a.mSignal, a.mHorizon);

    createDirIfNeeded("logs");
    createDirIfNeeded("logs/" + a.mBenchName);
    logfilename = "logs/" + a.mBenchName + "/PyAF_" + a.getName()+ ".log";
    logfile = open(logfilename, 'w');    
    sys.stdout = logfile    
    sys.stderr = logfile
    set_pyaf_logger(logfilename)
    
    try:
        tester = cGeneric_OneSignal_Tester(a.mTSSpec , a.mBenchName);
        tester.mTestCodeGeneration = False;
        tester.mParallelMode = False;
        tester.testSignal(a.mSignal, a.mHorizon)
        print("BENCHMARK_SUCCESS '" + a.getName() + "'");
        a.mResult = tester;
    except cBenchmarkError as error:
        print("BENCHMARKING_ERROR '" + a.getName() + "' : " + str(error));
    except MemoryError:
        print("BENCHMARK_MEMORY_FAILURE '" + a.getName() + "'");
    except:
        print("BENCHMARK_FAILURE '" + a.getName() + "'");
        # raise
    logfile.close();
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    return a;

class cGeneric_Tester_Arg:
    def __init__(self , bench_name, tsspec, sig, horizon):
        self.mBenchName = bench_name;
        self.mSignal = sig;
        self.mTSSpec = tsspec;
        self.mHorizon = horizon
        self.mResult = None;
        
    def getName(self):
        return self.mBenchName + "_" + self.mSignal + "_" + str(self.mHorizon);


class cGeneric_OneSignal_Tester:

    '''
    '''
        
    def __init__(self , tsspec, bench_name):
        print("BENCH_DATA" , bench_name)
        self.mTSSpec = tsspec;
        self.mTrainDataset = {};
        self.mAutoForecastBySignal = {}
        self.mTrainPerfData = {}
        self.mTestPerfData = {}
        self.mTrainTime = {};
        self.mBenchName = bench_name;
        self.mTestCodeGeneration = False;
        self.mTestIdempotency = False;
        self.mParallelMode = True;

    def reportTrainingDataInfo(self, iSignal, iHorizon):
        df = self.mTrainDataset[iSignal  + "_" + str(iHorizon)];
        lDate = self.mTSSpec.mTimeVar
        print("TIME : ", lDate  , "N=", df[lDate].shape[0], "H=", iHorizon,
              "HEAD=", df[lDate].head().values, "TAIL=", df[lDate].tail().values);
        print("SIGNAL : ", iSignal , "N=", df[iSignal].shape[0], "H=", iHorizon,
              "HEAD=", df[iSignal].head().values, "TAIL=", df[iSignal].tail().values);
        # df.to_csv("bench.csv");
        print(df.head());
        print(df.info());


    def getTrainingDataset(self, iSignal, iHorizon):
        df = pd.DataFrame();
        lSignalDataset = self.mTSSpec.mFullDataset;
        lFullDF = lSignalDataset[ [iSignal , self.mTSSpec.mTimeVar] ].dropna()
        #.astype(np.double)
        N = lFullDF.shape[0]
        # iHorizon = iHorizon; #self.mTSSpec.mHorizon[iSignal]
        lSize = N - iHorizon;
        if(N <= iHorizon):
            lSize = N
        df = lFullDF[0: lSize];
            
        self.mTrainDataset[iSignal  + "_" + str(iHorizon)] = df;
        self.reportTrainingDataInfo(iSignal, iHorizon);

    def reportModelInfo(self, iModel):
        iModel.getModelInfo();
        print(iModel.mSignalDecomposition.mTrPerfDetails)
        
    def trainModel(self, iSignal, iHorizon):
        df = self.mTrainDataset[iSignal  + "_" + str(iHorizon)];
        lAutoF1 = autof.cForecastEngine();
        lAutoF1.mOptions.mParallelMode = self.mParallelMode;
        self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)] = lAutoF1
        lAutoF1.train(df , self.mTSSpec.mTimeVar , iSignal, iHorizon)
        self.reportModelInfo(lAutoF1);
        print(lAutoF1.mSignalDecomposition.mTrPerfDetails.head());

    def computeModelPerfOnTraining(self, iModel):
        lPerfData = pd.DataFrame()
        lPerfData = lPerfData.append(iModel.mSignalDecomposition.mTrPerfDetails)
        lPerfData.reset_index(inplace = True)
        #lPerfData.plot.line('level_0', 'ForecastMAPE')
        self.mTrainPerfData[iSignal] = lPerfData;

    def trainSignal(self, iSignal, iHorizon):
        self.getTrainingDataset(iSignal, iHorizon);
        self.trainModel(iSignal, iHorizon);
        

    def testSignal(self, iSignal, iHorizon):
        start_time = time.time()
        self.trainSignal(iSignal, iHorizon);
        self.getTestPerfs(iSignal, iHorizon);
        end_time = time.time()
        self.mTrainTime[iSignal  + "_" + str(iHorizon)] = end_time - start_time;
        self.dumpForecastPerfs(iSignal, iHorizon);
        if(self.mTestIdempotency):
            self.testIdempotency(iSignal, iHorizon);

    def getApplyInDatset(self, iSignal, iHorizon):
        self.mApplyIn = pd.DataFrame();
        lSignalDataset = self.mTSSpec.mFullDataset;
        lFullDF = lSignalDataset[[iSignal , self.mTSSpec.mTimeVar]].dropna();
        #.astype(np.double)
        N = lFullDF.shape[0]
        lSize = N - iHorizon;
        if(N <= iHorizon):
            lSize = N
        self.mApplyIn = lFullDF[0: lSize];
        #self.mApplyIn.to_csv(iSignal + "_applyIn.csv");

    def applyModel(self, iSignal, iHorizon):
        lAutoF = self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)]
        lAutoF1 = self.pickleModel(lAutoF)
        self.mApplyOut = lAutoF1.forecast(self.mApplyIn, iHorizon);
        #self.mApplyOut.to_csv(iSignal + "_applyOut.csv");
        # print(self.mApplyOut.tail());
        assert(self.mApplyOut.shape[0] == (iHorizon + self.mApplyIn.shape[0]));

    def reportActualAndPredictedData(self, iSignal, iHorizon):
        print("FORECAST_DETAIL_ACTUAL" , self.mTSSpec.mName , iSignal ,
              [self.mActual.values[h] for h in range(iHorizon)]);
        print("FORECAST_DETAIL_PREDICTED" , self.mTSSpec.mName , iSignal ,
              [self.mPredicted.values[h] for h in range(iHorizon)]);
        assert(self.mActual.shape[0] == iHorizon);
        assert(self.mPredicted.shape[0] == iHorizon);
        # print(self.mActual.describe());
        # print(self.mPredicted.describe());
        # print(self.mActual.tail());
        # print(self.mPredicted.tail());

    def computePerfOnForecasts(self, iSignal, iHorizon):
        lAutoF1 = self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)]
        lForecastPerf = lAutoF1.computePerf(self.mActual, self.mPredicted, self.mBenchName + "_" + self.mTSSpec.mName + "_" + iSignal );
        self.mTestPerfData[iSignal  + "_" + str(iHorizon)] = lForecastPerf;


    def summary(self):
        str1 = "";
        for k in self.mTestPerfData.keys():
            lAutoF1 = self.mAutoForecastBySignal[k]
            lModelFormula = lAutoF1.mSignalDecomposition.mBestModel.getFormula();
            N  = self.mTrainDataset[k].shape[0]
            lPerf = self.mTestPerfData[k];
            str1 = str(k) + " " + str(N) + " '" + lModelFormula + "' ";
            str1 = str1 + str(lPerf.mCount) + " " +  str(lPerf.mMAPE);
            str1 = str1 + " " + str(lPerf.mSMAPE) + " " + str(lPerf.mMASE) + " " +  str(lPerf.mL1) + " " + str(lPerf.mL2) + " " +  str(lPerf.mR2) + "\n";            
        return str1;


    def pickleModel(self, iModel):
        import pickle
        output = pickle.dumps(iModel)
        lReloadedObject = pickle.loads(output)
        output2 = pickle.dumps(lReloadedObject)    
        assert(iModel.to_json() == lReloadedObject.to_json())
        return lReloadedObject;

    def generateCode(self, iSignal, iHorizon):
        lAutoF = self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)]
        lCodeGenerator = tscodegen.cTimeSeriesCodeGenerator();
        lSQL = lCodeGenerator.testGeneration(lAutoF);
        del lCodeGenerator;

    def getTestPerfs(self, iSignal, iHorizon):
        self.getApplyInDatset(iSignal, iHorizon);
        self.applyModel(iSignal, iHorizon);
        lSignalDataset = self.mTSSpec.mFullDataset;
        lFullDF = lSignalDataset[iSignal].dropna()
        self.mActual = lFullDF.tail(iHorizon).reset_index(drop = True);
        self.mPredicted = self.mApplyOut[iSignal + '_Forecast'].tail(iHorizon).reset_index(drop = True);
        print(iHorizon , self.mActual.head(iHorizon));
        print(iHorizon , self.mPredicted.head(iHorizon));
        self.reportActualAndPredictedData(iSignal, iHorizon);
        self.computePerfOnForecasts(iSignal, iHorizon);
        if(self.mTestCodeGeneration):
            self.generateCode(iSignal, iHorizon);
        
    def dumpForecastPerfs(self, iSignal, iHorizon):
        lAutoF1 = self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)]
        lPerf = self.mTestPerfData[iSignal  + "_" + str(iHorizon)];
        print("BENCHMARK_PERF_DETAIL_SIGNAL_HORIZON", self.mTSSpec.mName , iSignal,
              self.mTrainDataset[iSignal  + "_" + str(iHorizon)].shape[0] ,
              iHorizon);
        print("BENCHMARK_PERF_DETAIL_BENCH_TIME_IN_SECONDS", "PYAF_SYSTEM_DEPENDENT_", self.mTSSpec.mName , iSignal,
              str(self.mTrainTime[iSignal  + "_" + str(iHorizon)]));        
        print("BENCHMARK_PERF_DETAIL_BEST_MODEL", self.mTSSpec.mName , iSignal,
              lAutoF1.mSignalDecomposition.mBestModel.getFormula());
        print("BENCHMARK_PERF_DETAIL_PERF_COUNT", self.mTSSpec.mName , iSignal,
              lPerf.mCount);
        print("BENCHMARK_PERF_DETAIL_PERF_MAPE_SMAPE_MASE", self.mTSSpec.mName , iSignal,
              lPerf.mMAPE,  lPerf.mSMAPE, lPerf.mMASE);
        print("BENCHMARK_PERF_DETAIL_PERF_L1_L2_R2", self.mTSSpec.mName , iSignal,
              lPerf.mL1,  lPerf.mL2,  lPerf.mR2);
        pass

    def testSignalIdempotency(self, iSignal, iHorizon, tr, cy, ar):
        lAutoF1 = self.mAutoForecastBySignal[iSignal  + "_" + str(iHorizon)];
        lApplyOut = self.mApplyOut.head(self.mApplyIn.shape[0]);
        print(lApplyOut.columns);
        lNewSignal = iSignal + "_" + str(tr) + "_" + str(cy) + "_" + str(ar);
        lTransformedSignal = lAutoF1.mSignalDecomposition.mBestModel.mSignal;
        lSignal = 0.0 * lApplyOut[iSignal];
        if(tr is not None):
            lSignal = lSignal + lApplyOut[lTransformedSignal + "_Trend"];
        if(cy is not None ):
            lSignal = lSignal + lApplyOut[lTransformedSignal + "_Cycle"];
        if(ar is not None ):
            lSignal = lSignal + lApplyOut[lTransformedSignal + "_AR"];
        df= pd.DataFrame();
        df[self.mTSSpec.mTimeVar] = lApplyOut[self.mTSSpec.mTimeVar];
        df[lNewSignal] = lSignal;
        lAutoF1 = autof.cForecastEngine();
        lAutoF1.mOptions.mParallelMode = self.mParallelMode;
        lAutoF1.train(df , self.mTSSpec.mTimeVar , lNewSignal, iHorizon)
        self.reportModelInfo(lAutoF1);

    def testIdempotency(self, iSignal, iHorizon):
        for tr in [None , "TR"]:
            for cy in [None , "CY"]:
                for ar in [None , "AR"]:
                    if((tr is not None) or (cy is not None) or (ar is not None)):
                        self.testSignalIdempotency(iSignal, iHorizon, tr, cy, ar);

class cGeneric_Tester:
    '''
    test a collection of signals
    '''

    def __init__(self , tsspec, bench_name):
        # print("BENCH_DATA" , bench_name, tsspec)
        self.mTSSpec = tsspec;
        self.mBenchName = bench_name;
        self.mTestCodeGeneration = False;
        self.mTestIdempotency = False;
        self.mType = "OneDataFramePerSignal";
        if(hasattr(self.mTSSpec , "mFullDataset")):
            self.mType = "OneDataFrameForAllSignals";
        print("BENCH_TYPE" , bench_name, self.mType);
        self.fillSignalInfo();

    def fillSignalInfo(self):
        self.mTSSpecPerSignal = {};
        if(self.mType == "OneDataFrameForAllSignals"):
            lTSSpec = self.mTSSpec;
            for sig in self.mTSSpec.mFullDataset.columns:
                if(sig != lTSSpec.mTimeVar):
                    self.mTSSpecPerSignal[sig] = self.mTSSpec;
        else:
            self.mTSSpecPerSignal = self.mTSSpec;

    def testAllSignals(self, iHorizon):
        for sig in self.mTSSpecPerSignal.keys():
            lSpec = self.mTSSpecPerSignal[sig]
            # print(lSpec.__dict__)
            lHorizon = lSpec.mHorizon[sig]
            tester = cGeneric_OneSignal_Tester(lSpec, self.mBenchName);
            tester.mParallelMode = False;
            tester.testSignal(sig, lHorizon);
            del tester;
        pass
    
    def testSignals(self, iSignals, iHorizon = 2):
        sigs = iSignals.split(" ");
        for sig in sigs:
            if(sig in self.mTSSpecPerSignal.keys()):
                lSpec = self.mTSSpecPerSignal[sig]
                # print(lSpec.__dict__)
                lHorizon = lSpec.mHorizon[sig]
                tester = cGeneric_OneSignal_Tester(lSpec, self.mBenchName);
                tester.testSignal(sig, lHorizon);
                tester.mParallelMode = True;
                del tester;
            else:
                raise cBenchmarkError("UNKNOWN_SIGNAL '" + sig + "'");
                pass;
        pass


    def run_multiprocessed(self, nbprocesses = None):
        if(nbprocesses is None):
            nbprocesses = (mp.cpu_count() * 3) // 4;
        pool = mp.Pool(processes=nbprocesses, maxtasksperchild=None)
        args = []
        for sig in self.mTSSpecPerSignal.keys():
            lSpec = self.mTSSpecPerSignal[sig]
            # print(lSpec.__dict__)
            lHorizon = lSpec.mHorizon[sig]
            a = cGeneric_Tester_Arg(self.mBenchName, lSpec, sig , lHorizon);
            args = args + [a];

        lResults = {};
        i = 1;
        for res in pool.imap(run_bench_process, args):
            print("FINISHED_BENCH_FOR_SIGNAL" , self.mBenchName, res.mSignal , i , "/" , len(args));
            lResults[res.mSignal] = res.mResult.summary();
            i = i + 1;
            del res
        
        pool.close()
        pool.join()

        for (name, summary) in lResults.items():
            print("BENCH_RESULT_DETAIL" ,  self.mBenchName, name, summary);
