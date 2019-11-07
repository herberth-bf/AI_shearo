# -*- coding: utf-8 -*-
"""
Created on Sun Oct 27 17:36:14 2019

Dataset Building
raw phase images as input
deviations arrays as outputs

@author: Herberth Frohlich
"""
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from sklearn.metrics import mean_absolute_error, r2_score

# Paths
sys.path.append(r'D:\Users\Herberth Frohlich\Documents\AI_shearo\notebooks\modelling')
save_path = (r'D:\Users\Herberth Frohlich\Documents\AI_shearo\dataset\processed')

# Importing users methods
from Helpers import Loaders
load = Loaders()# use load_images
from FeatureExtractors import FeatureExtractors
extract = FeatureExtractors() # use deviations
from Processing import Processing
process = Processing() # use lowess_smooth
from Processing import FeatureReduction
reduction = FeatureReduction() # use pca_
from Helpers import Metrics
metrics = Metrics() #use mean_absolute_percentage_error
from RegressionMethods import RegressionMethods
regression = RegressionMethods() #import RandomForestRegressor, GradientBoostingRegressor etc

# Loading Shearography Images
trainPath = (r"D:\MachineLearningInOpticsExtrapolation\NoDecompositionRegressionFull\TrainSet")
testPath = (r"D:\MachineLearningInOpticsExtrapolation\NoDecompositionRegressionFull\TestSet")
valPath = (r"D:\MachineLearningInOpticsExtrapolation\NoDecompositionRegressionFull\ValSet")
trainAttrX = pd.read_csv(os.path.join(trainPath, "trainEnergies.txt"), header=None)
testAttrX = pd.read_csv(os.path.join(testPath, "testEnergies.txt"), header=None)
valAttrX = pd.read_csv(os.path.join(valPath, "valEnergies.txt"), header=None)

# making sure they are in ascending order and other preprocessing
maxEnergy = trainAttrX[0].max() 
y_train = trainAttrX[0]# / maxEnergy
y_test = testAttrX[0]# / maxEnergy
y_val = valAttrX[0]# / maxEnergy
indxTest = np.argsort(y_test)
indxVal = np.argsort(y_val)

def feature_acquisition(dim):
    images_train, files_train = load.load_images(trainPath, dim)
    trainImagesX = images_train / 255.0
    images_test, files_test = load.load_images(testPath, dim)
    testImagesX = images_test / 255.0
    images_val, files_val = load.load_images(valPath, dim)
    valImagesX  = images_val / 255.0
    
    X_train = np.empty((0, dim[0]*2))
    for i in range(trainImagesX.shape[0]):
        im = trainImagesX[i, :, :]
        X_train = np.append(X_train, extract.deviations(im), axis=0)
        
    X_val = np.empty((0, dim[0]*2))    
    for i in range(valImagesX.shape[0]):
        im = valImagesX[i, :, :]
        X_val = np.append(X_val, extract.deviations(im), axis=0)

    X_test = np.empty((0, dim[0]*2))
    for i in range(testImagesX.shape[0]):
        im = testImagesX[i, :, :]
        X_test = np.append(X_test, extract.deviations(im), axis=0)
    return X_train, X_val, X_test

#%% GRID SEARCH DEVIATION + PCA
DIM = [(64, 64), (128, 128), (256, 256), (329, 329)] #dimensions for deviations
COMPONENTS = [0.8, 0.9, 1] # in terms of percentage of variance retained
N_ESTIMATORS = [30, 60, 120] # tree parameter
MAX_DEPTH = [3, 6, 12] # tree parameter
MIN_SAMPLES_SPLIT = [3, 4, 5] # tree parameter

numberOfScores = len(DIM)*len(COMPONENTS)*len(N_ESTIMATORS)*len(MAX_DEPTH)*len(MIN_SAMPLES_SPLIT)
#predMatrixFull = [[] for i in range(numberOfScores)]
scoresRF = np.zeros((numberOfScores, 8))
scoresGB = np.zeros((numberOfScores, 8))
scoresVoting = np.zeros((numberOfScores, 8))
count=0

for d in DIM:
    X_train, X_val, X_test = feature_acquisition(d)
    
    for c in COMPONENTS:
        # calculate the maximum number of components for the grid search then keep some of them
        X_train_USE, X_test_USE, X_val_USE, pca = reduction.pca_(X_train, X_test, X_val, n=X_train.shape[1])
        cumulative = np.cumsum(pca.explained_variance_ratio_)
        index = np.argmax(cumulative>=c)
        X_train_USE = X_train_USE[:, index:]
        X_val_USE = X_val_USE[:, index:]
        X_test_USE = X_test_USE[:, index:]
        
        for n in N_ESTIMATORS:
            for m in MAX_DEPTH:
                for s in MIN_SAMPLES_SPLIT:
                    
                    #print("Count:{} --> Dimension {}, Component {}, Estimators {}, Max Depth {}, Min Sample Split {}".format(count, d, c, n, m, s))
                    # Fitting the model: random forest
                    reg1, reg1n = regression.RandomForestRegressor(X_train_USE, y_train, n_estimators=n, oob_score=True, 
                                                            verbose=0, max_depth=m, min_samples_split=s)    
                    
                    # Fitting the model: gradient boosting
                    reg2, reg2n = regression.GradientBoostingRegressor(X_train_USE, y_train,n_estimators=n,
                                                                max_depth=m, min_samples_split=s)    
                    
                    # Averaged by voting
                    estimators = [('rf', reg1n), ('gb', reg2n)]
                    ereg = regression.VotingRegressor(X_train_USE, y_train, *estimators)
                    ereg.fit(X_train_USE, y_train)
                    
                    # Validation
                    y_pred_reg1 = reg1.predict(X_val_USE)
                    y_pred_reg2 = reg2.predict(X_val_USE)
                    y_pred_ereg = ereg.predict(X_val_USE)
                    
                    # Scores Random Forest
                    scoresRF[count, 0] = mean_absolute_error(y_val, y_pred_reg1) # MAE
                    scoresRF[count, 1] = metrics.mean_absolute_percentage_error(y_val, y_pred_reg1) # MAPE
                    scoresRF[count, 2] = r2_score(y_val, y_pred_reg1) # SCORE
                    scoresRF[count, 3] = d[0]
                    scoresRF[count, 4] = c
                    scoresRF[count, 5] = n
                    scoresRF[count, 6] = m
                    scoresRF[count, 7] = s
                    
                    # Scores Gradient Boosting
                    scoresGB[count, 0] = mean_absolute_error(y_val, y_pred_reg2) # MAE
                    scoresGB[count, 1] = metrics.mean_absolute_percentage_error(y_val, y_pred_reg2) # MAPE
                    scoresGB[count, 2] = r2_score(y_val, y_pred_reg2) # SCORE
                    scoresGB[count, 3] = d[0]
                    scoresGB[count, 4] = c
                    scoresGB[count, 5] = n
                    scoresGB[count, 6] = m
                    scoresGB[count, 7] = s
                    
                    # Scores Voting Regression
                    scoresVoting[count, 0] = mean_absolute_error(y_val, y_pred_ereg) # MAE
                    scoresVoting[count, 1] = metrics.mean_absolute_percentage_error(y_val, y_pred_ereg) # MAPE
                    scoresVoting[count, 2] = r2_score(y_val, y_pred_ereg) # SCORE
                    scoresVoting[count, 3] = d[0]
                    scoresVoting[count, 4] = c
                    scoresVoting[count, 5] = n
                    scoresVoting[count, 6] = m
                    scoresVoting[count, 7] = s
                               
                    print("Count {} --> MAE RF {}, \ GB {} \ Voting {},".format(count, np.round(scoresRF[count, 0],2), 
                          np.round(scoresGB[count, 0],2), np.round(scoresVoting[count, 0],2)))
                    count+=1

# Save corresponding matrices
#np.save(os.path.join(save_path,"scoresRF_dev+pca+rf"), scoresRF)
#np.save(os.path.join(save_path,"scoresGB_dev+pca+rf"), scoresGB)
#np.save(os.path.join(save_path,"scoresVoting_dev+pca+rf"), scoresVoting)
#np.save("predMatrixFull_dev+pca+rf", predMatrixFull)                   
#%% Retrieving scores
scoresRF = np.load(os.path.join(save_path,"scoresRF_dev+pca+rf.npy"))
scoresGB = np.load(os.path.join(save_path,"scoresGB_dev+pca+rf.npy"))
scoresVoting = np.load(os.path.join(save_path,"scoresVoting_dev+pca+rf.npy"))
#%% BEst models
indexBestModel = np.argmin(scoresVoting[:, 0])
dimBest = (int(scoresVoting[indexBestModel, 3]), int(scoresVoting[indexBestModel, 3]))
cBest = int(scoresVoting[indexBestModel, 4])
nBest = int(scoresVoting[indexBestModel, 5])
mBest = int(scoresVoting[indexBestModel, 6])
sBest = int(scoresVoting[indexBestModel, 7])

X_train, X_val, X_test = feature_acquisition(dimBest)
X_train_USE, X_test_USE, X_val_USE, pca = reduction.pca_(X_train, X_test, X_val, n=X_train.shape[1])
cumulative = np.cumsum(pca.explained_variance_ratio_)
index = np.argmax(cumulative>=cBest)
X_train_USE = X_train_USE[:, index:]
X_val_USE = X_val_USE[:, index:]
X_test_USE = X_test_USE[:, index:]
reg1_best, reg1n_best = regression.RandomForestRegressor(n_estimators=nBest, 
                                                         max_depth=mBest, 
                                                         min_samples_split=sBest)

reg2_best, reg2n_best = regression.GradientBoostingRegressor(n_estimators=nBest, 
                                                             max_depth=mBest, 
                                                             min_samples_split=sBest)

y_pred_reg1_best = reg1_best.predict(X_val_USE)
y_pred_reg2_best = reg2_best.predict(X_val_USE)
reg1_mae_best = mean_absolute_error(y_val, y_pred_reg1_best)
reg2_mae_best = mean_absolute_error(y_val, y_pred_reg2_best)

#%% Automatic weighting by optimization
# TODO SUBSTITUIR PELA FUNCAO IMPLEMENTADA EM SERVICO
dic = [('gb', reg1_best), ('rf', reg2_best)]
def fun(x):    
    ereg = regression.VotingRegressor(X_train_USE, y_train, weights = x, *dic, )#[0.19, 0.51, 0.30]
    ereg.fit(X_train_USE, y_train)
    ereg_mae = mean_absolute_error(y_val, ereg.predict(X_val_USE))
    return ereg_mae

cons = ({'type': 'eq', 'fun': lambda x:  x[0] + x[1] - 1})
bnds = ((0, 1), (0, 1))

x = [0.5, 0.5]
result = minimize(fun, x, method="SLSQP", bounds=bnds, constraints=cons, tol=1e-2)

if result.success:
    fitted_params = result.x
    print(fitted_params)
else:
    raise ValueError(result.message)

#%% Voting fiting 
dic = [('rf', reg1_best), ('gb', reg2_best)]
ereg = VotingRegressor(dic, weights = fitted_params)#[0.19, 0.51, 0.30]
ereg.fit(X_train_USE, y_train)
ereg_mae = mean_absolute_error(y_val, ereg.predict(X_val_USE))
print('RandomForest {}, GB {}, Voting Regressor {}'.format(reg1_mae_best, reg2_mae_best, ereg_mae))

#%%

ereg_best = VotingRegressor([('rf', reg1_best), ('gb', reg2_best)])
ereg_best.fit(X_train_USE, y_train)

import pickle
filename = 'dev+pca+voting.sav'
pickle.dump(ereg_best, open(filename, 'wb'))

#%% Interpolation and testing - model proofing    
#ereg_best = pickle.load(open(filename, 'rb'))           
# Testing interpolation
y_predT = ereg_best.predict(X_test_USE)
testMAE = mean_absolute_error(y_test, y_predT)
testMAPE = mean_absolute_percentage_error(y_test, y_predT)
testScore = r2_score(y_test, y_predT) 
print(testMAE, testMAPE)
y_test_ = y_test[indxTest]
y_predT = y_predT[indxTest]


# TODO SEARCH FOR THE BEST PARAMETERS INSIDE SCORE MATRI

fig, axs = plt.subplots(nrows=1, ncols=1, sharex=False)
#ax = axs[0]
#ax.scatter(np.arange(len(y_val_.values)), y_val_.values, s=5)
#ax.scatter(np.arange(len(y_pred)), y_pred, s=15)
#ax.set_title("ValSet - MAPE: {}, R2Score: {}".format(np.round(valMAPE,3), np.round(valScore,3)))
#ax.set_ylabel("Energy[J]")
#ax.set_xlabel("Observations")

tipo = "DEV + PCA +  RF - voting"
ax = axs
ax.scatter(np.arange(len(y_test_.values)), y_test_.values, s=5)
ax.scatter(np.arange(len(y_predT)), y_predT, s=15)
ax.set_title("TestSet - MAE: {}, MAPE: {}".format(np.round(testMAE,3), np.round(testMAPE,3)))
ax.set_ylabel("Energy[J]")
ax.set_xlabel("Observations")
fig.suptitle("TYPE: {}, IMG DIM: {}, N_ESTIMATORS: {}, MAX_DEPTH: {}, LEAF_SIZE: {} ".format(tipo, dimBest[0], nBest, mBest, sBest))
plt.show()

#%%
# TODO GRID SEARCH
# TODO ERROR BAR PLOT
    
    




