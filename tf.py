import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as numpy
import pandas as pd
import tensorflow as tf
from pandas import DataFrame
from pandas import Series
from pandas import concat
from pandas import read_csv
from pandas import datetime
from datetime import datetime as pyDatetime
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import LSTM
from math import sqrt, floor
from matplotlib import pyplot
from datetime import timedelta

SCOPE = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
CREDS = ServiceAccountCredentials.from_json_keyfile_name('learn-app-engine-d352d8131754.json', SCOPE)

# date-time parsing function for loading the dataset
def parser(x):
	return datetime.strptime('190'+x, '%Y-%m')

# calculates simple moving avg
def sMovingAvg(recCount):
    return recCount.rolling(window=5).mean()

# frame a sequence as a supervised learning problem
def timeseries_to_supervised(data, lag=1):
	df = DataFrame(data)
	columns = [df.shift(i) for i in range(1, lag+1)]
	columns.append(df)
	df = concat(columns, axis=1)
	df.fillna(0, inplace=True)
	return df

# create a differenced series
def difference(dataset, interval=1):
	diff = list()
	for i in range(interval, len(dataset)):
		value = dataset[i] - dataset[i - interval]
		diff.append(value)
	return Series(diff)

# invert differenced value
def inverse_difference(history, yhat, interval=1):
	return yhat + history[-interval]

# scale train and test data to [-1, 1]
# def scale(trainDF, testDF):
# scale train and test data to [-1, 1]
def scale(train, test):
	# fit scaler
	scaler = MinMaxScaler(feature_range=(-1, 1))
	scaler = scaler.fit(train)
	# transform train
	train = train.reshape(train.shape[0], train.shape[1])
	train_scaled = scaler.transform(train)
	# transform test
	test = test.reshape(test.shape[0], test.shape[1])
	test_scaled = scaler.transform(test)
	return scaler, train_scaled, test_scaled
 
# inverse scaling for a forecasted value
def invert_scale(scaler, X, value):
	new_row = [x for x in X] + [value]
	array = numpy.array(new_row)
	array = array.reshape(1, len(array))
	inverted = scaler.inverse_transform(array)
	return inverted[0, -1]
 
# fit an LSTM network to training data
def fit_lstm(train, batch_size, nb_epoch, neurons):
	X, y = train[:, 0:-1], train[:, -1]
	X = X.reshape(X.shape[0], 1, X.shape[1])
	model = Sequential()
	model.add(LSTM(neurons, batch_input_shape=(batch_size, X.shape[1], X.shape[2]), stateful=True))
	model.add(Dense(1))
	model.compile(loss='mean_squared_error', optimizer='adam')
	for i in range(nb_epoch):
		model.fit(X, y, epochs=1, batch_size=batch_size, verbose=0, shuffle=False)
		model.reset_states()
	return model

# make a one-step forecast
def forecast_lstm(model, batch_size, X):
	X = X.reshape(1, 1, len(X))
	yhat = model.predict(X, batch_size=batch_size)
	return yhat[0,0]

def timeSeries():
    client = gspread.authorize(CREDS)
    sheet = client.open("pytest").worksheet("sheet")
    ws = sheet.get_all_records()
    df = pd.DataFrame(ws)
    df['premier_upgrade_date'] = pd.to_datetime(df['premier_upgrade_date'])
    df = df.sort_values(by='premier_upgrade_date', ascending=True)
    maxDateList = df['premier_upgrade_date'].tail(1).to_string().split(' ')
    maxDateStr = maxDateList[len(maxDateList)-1]

    df['s_moving_avg'] = sMovingAvg(df['rec_count'])
    df =  df.dropna(subset=['s_moving_avg'])
    series = pd.Series(df['s_moving_avg'], index= df.index)
   
    # transform data to be stationary
    raw_values = series.values
    diff_values = difference(raw_values, 1)
    supervised = timeseries_to_supervised(series, 1)
    supervised_values = supervised.values

    train, test = supervised_values[0:-10], supervised_values[-10:]
    # transform the scale of the data
    scaler, train_scaled, test_scaled = scale(train, test)
    # fit the model
    lstm_model = fit_lstm(train_scaled, 1, 200, 2)
    # forecast the entire training dataset to build up state for forecasting
    train_reshaped = train_scaled[:, 0].reshape(len(train_scaled), 1, 1)
    lstm_model.predict(train_reshaped, batch_size=1)

    # walk-forward validation on the test data
    predictions = list()
    test_scaledLen = len(test_scaled)
    totalRows = sheet.col_count
    sheet.resize(totalRows + test_scaledLen)

    for i in range(test_scaledLen):
        # make one-step forecast
        X, y = test_scaled[i, 0:-1], test_scaled[i, -1]
        yhat = forecast_lstm(lstm_model, 1, X)
        # invert scaling
        yhat = invert_scale(scaler, X, yhat)
        # invert differencing
        yhat = inverse_difference(raw_values, yhat, len(test_scaled)+1-i)
        # store forecast
        expected = raw_values[len(train) + i]
   
        maxDate = datetime.strptime(maxDateStr, '%Y-%m-%d')
        predictionDate = maxDate + timedelta(days=i+1)
        predictionDateStr = predictionDate.strftime('%m/%d/%Y')

        prediction = [predictionDateStr, 1, floor(yhat)]
        predictions.append(prediction)
        sheet.append_row(prediction)
        print({'day':i+1, 'predicted':yhat, 'expected': expected})

    #sheet.append_row(predicted_value)
    # line plot of observed vs predicted
    #df.plot(x='premier_upgrade_date', y='rec_count', color='blue')
    #df.plot(x='premier_upgrade_date', y='s_moving_avg', color='red')
    #pyplot.show()
    return 'time series prediction done'

#if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    #pushResults()
   # timeSeries()
# [END gae_python37_app]
