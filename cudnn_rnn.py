"""CUDNN RNN Test."""
import theano
import theano.tensor as T
from theano.gpuarray import dnn
from theano.gpuarray.type import gpuarray_shared_constructor
import numpy as np
import argparse
import time

mode_with_gpu = theano.compile.mode.get_default_mode().including(
    'gpuarray'
).excluding('gpu')

parser = argparse.ArgumentParser()
parser.add_argument(
    "-n",
    "--network",
    help="network type rnn/lstm/gru",
    required=True
)
parser.add_argument(
    "-d",
    "--depth",
    help="num layers",
    type=int,
    required=True
)
parser.add_argument(
    "-b",
    "--batch_size",
    type=int,
    help="batch size",
    required=True
)
parser.add_argument(
    "-o",
    "--hidden",
    type=int,
    help="hidden dim",
    required=True
)
parser.add_argument(
    "-t",
    "--seq_len",
    type=int,
    help="time steps",
    required=True
)
parser.add_argument(
    "-md",
    "--mode_dir",
    type=int,
    help="Bidirectional",
    required=True
)
args = parser.parse_args()
network_type = args.network
depth = args.depth
batch_size = args.batch_size
hidden_dim = args.hidden
seq_len = args.seq_len
mode_dir = args.mode_dir
num_passes = 1000

x_val = np.random.random((seq_len, batch_size, hidden_dim)).astype(
    theano.config.floatX
)
y_val = np.random.random((seq_len, batch_size, hidden_dim)).astype(
    theano.config.floatX
)
h0_val = np.random.random((depth * mode_dir, batch_size, hidden_dim)).astype(
    theano.config.floatX
)
c0_val = np.random.random((depth * mode_dir, batch_size, hidden_dim)).astype(
    theano.config.floatX
)

start = time.time()

X = T.tensor3('X')
Y = T.tensor3('Y')
h0 = T.tensor3('h0')
c0 = T.tensor3('c0')

rnnb = dnn.RNNBlock(
    theano.config.floatX,
    hidden_dim,
    depth,
    network_type,
    input_mode='linear',
    direction_mode='unidirectional' if mode_dir == 1 else
    'bidirectional'
)
psize = rnnb.get_param_size([batch_size, hidden_dim])
params_cudnn = gpuarray_shared_constructor(
    np.zeros((psize,), dtype=theano.config.floatX)
)
print psize

"""
for i in range(depth):
    dnn_params = rnnb.split_params(params_cudnn, i,
                                   [batch_size, hidden_dim])
    for pidx in range(len(dnn_params)):
        print dnn_params[pidx].shape
"""

# lstm = LSTM(input_dim, hidden_dim)
if network_type == 'lstm':
    output = rnnb.apply(params_cudnn, X, h0, c0)[0]  # Only hidden states
    params_rnn = {X: x_val, h0: h0_val, c0: c0_val}
    params_rnn_grad = {X: x_val, Y: y_val, h0: h0_val, c0: c0_val}
else:
    output = rnnb.apply(params_cudnn, X, h0)[0]  # Only hidden states
    params_rnn = {X: x_val, h0: h0_val}
    params_rnn_grad = {X: x_val, Y: y_val, h0: h0_val}

cost = T.mean((Y - output) ** 2)
grads = T.grad(cost, params_cudnn)
cudnn_fn = theano.function(
    inputs=[],
    outputs=output,
    mode=mode_with_gpu,
    givens=params_rnn)
cudnn_fn()
cudnn_grad_fn = theano.function(
    inputs=[],
    outputs=grads,
    mode=mode_with_gpu,
    givens=params_rnn_grad
)

cudnn_grad_fn()
theano.sandbox.cuda.synchronize()
print "Setup : compile + forward/backward x 1"
print "--- %s seconds" % (time.time() - start)

num_processed = num_passes * batch_size
start = time.time()
for i in xrange(0, num_passes):
    cudnn_fn()
theano.sandbox.cuda.synchronize()
end = time.time()
print "Forward:"
print "--- %i samples in %s seconds (%f samples/s, %.7f s/sample) ---" % (
    num_processed,
    end - start,
    num_processed / (end - start),
    (end - start) / num_processed
)

start = time.time()
for i in xrange(0, num_passes):
    cudnn_grad_fn()
theano.sandbox.cuda.synchronize()
end = time.time()
print "Forward + Backward:"
print "--- %i samples in %s seconds (%f samples/s, %.7f s/sample) ---" % (
    num_processed,
    end - start,
    num_processed / (end - start),
    (end - start) / num_processed
)
