#!/usr/bin/python
import pyopencl as cl
import optparse
import random
import struct
import numpy
import time
import math
import sys

# Function to prompt for device selection
def askLongOptions(prompt,options):
    print("{0}:".format(prompt))
    for i,o in enumerate(options):
        print("\t{0}: {1}".format(i,o))
    while 1:
        x = raw_input('? ')
        try:
            x = int(x)
        except ValueError:
            print("Error: choose a number between 0 and {0}.".format(len(options)))
            continue
        if x < 0 or x >= len(options):
            print("Error: choose a number between 0 and {0}.".format(len(options)))
            continue
        return options[x]

# Used to round the global work size up to a tile boundary
# e.g. roundUpToIncrements(30,16) = 32
def roundUpToIncrements(inp,inc):
    if inp % inc == 0: return inp
    return inc * (int(inp/inc) + 1)

# Find a list of platforms on the machine, then return a list of the first platform's devices
def getDevices():
    platforms = cl.get_platforms()
    assert len(platforms) >= 1, "No CL platforms found."
    if len(platforms) > 1:
	print "Warning: we have {0} platforms. Selecting the first (zeroth) one.".format(len(platforms))
    devices = platforms[0].get_devices()
    return devices

# Handle command line options
parser = optparse.OptionParser()
parser.add_option("-d", "--device", # Which device to use?
    action="store", type=int, dest="device", default=None,
    help="which compute device to use (starts at 0)")
#~ parser.add_option("-w", "--width",
    #~ default=132, type=int, dest="width",
    #~ help="width of matrix (default: %default)")
#~ parser.add_option("-n", "--no-cpu",
    #~ default=True, action="store_false", dest="allowcpucompute",
    #~ help="prevent CPU computation")
(options, args) = parser.parse_args()
#width = options.width

# Select a device
devices = getDevices()
device = None
if options.device:
    if options.device < 0 or options.device >= len(devices):
	print "Invalid device selection: {0}.".format(options.device)
    else:
	device = devices[options.device]
	print "Selecting device {0}: {1}".format(options.device,device)
if len(devices) == 1:
    print "Selecting the first and only device."
    device = devices[0]
if not device:
    device = askLongOptions("Select a device",devices)

# Calculate optimal tile size -- largest power of two less than sqrt of max work group size
maxwgs = device.get_info(cl.device_info.MAX_WORK_GROUP_SIZE)
print "This device supports up to {0} threads per work group.".format(maxwgs)
tile_size = 2 ** int(math.log(int(math.sqrt(maxwgs)))/math.log(2))
	
#~ # Build matricies
#~ print
#~ print "Using Gaussian distribution with mean of %.2f and S.D. of %.2f" % (MEAN,STD_DEV)
#~ print "Generating matrix 1:",
#~ matrix1 = numpy.random.normal(loc=MEAN, scale=STD_DEV, size=(width)
#~ print matrix1.shape
#~ print "Generating matrix 2:",
#~ matrix2 = numpy.random.normal(loc=MEAN, scale=STD_DEV, size=(width,width))
#~ print matrix2.shape
#~ print

array1 = numpy.array([x/10.0 for x in xrange(0,100)])
array2 = array1.copy()
array3 = numpy.array([0])
width = len(array1)
height = len(array2)
depth = len(array3)
print "Working with arrays of dimensions ({0},{1},{2})".format(width,height,depth)

# Global work size - number of threads to run in total
#global_work_size = roundUpToIncrements(width,tile_size)

#print "Working on two %d x %d matrix; tile size: %d; global work size: %d" % (width,width,tile_size,global_work_size)

# Set up OpenCL
context = cl.Context([device],None,None) # Create a context
with open('ker.cl','r') as inp:
    kernel = inp.read();
#~ kernel = '''
#~ __kernel void matmult(__global const float *A, __global const float *B, __global float *output, const uint width) {
    #~ uint threadIDx = get_global_id(0); // unique across all blocks ("work groups") for a given kernel
    #~ uint threadIDy = get_global_id(1); // parameter is the dimension id
    #~ 
    #~ if(threadIDx >= width || threadIDy >= width)
	#~ return;
    #~ 
    #~ float value = 0;
    #~ for(uint i = 0; i < width; ++i)
	#~ value += A[threadIDx * width + i] * B[i * width + threadIDy];
    #~ output[threadIDx * width + threadIDy] += value;
#~ } '''

# Build a Program object -- kernel is compiled here, too. Can be cached for more responsiveness.
worker = cl.Program(context, kernel).build()
queue = cl.CommandQueue(context)

# Prepare input buffers
t = time.time() # Start timing the GL code
arr1_buf = cl.Buffer(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=array1.astype(numpy.float32))
arr2_buf = cl.Buffer(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=array2.astype(numpy.float32))
arr3_buf = cl.Buffer(context, cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR, hostbuf=array3.astype(numpy.float32))

# Allocate space for output buffer
output = numpy.zeros(width*height*depth,numpy.float32)
output_buf = cl.Buffer(context, cl.mem_flags.WRITE_ONLY | cl.mem_flags.USE_HOST_PTR, hostbuf=output)

# Start compute - call the matmult kernel function using command queue queue, 2d global work size as given, and 2d local work size as given
# Returns immediately -- we block at the enqueue_read_buffer
worker.WorleyNoise(queue, (width,height,depth), (10,10,1), 
	arr1_buf, arr2_buf, arr3_buf, output_buf, 
        numpy.int32(width), numpy.int32(height), numpy.int32(depth))

# Read output buffer back to host 
cl.enqueue_read_buffer(queue, output_buf, output).wait()

# Compute the GPU time
gputime = time.time() - t
print "gpu time: {0:8.2f}ms".format(gputime * 1000)

if depth != 1: raise Exception("Can't write 3d image as a PGM :)")
with open('output.pgm','w') as out:
    out.write('P2\n{0} {1}\n255\n'.format(width,height))
    for value in (output * 255).astype(numpy.uint32):
        out.write(str(value) + ' ')
    


#~ if options.allowcpucompute:
    #~ print "\nComputing on CPU"
    #~ # Begin timing the CPU code
    #~ t = time.time() 
    #~ 
    #~ # Calculate multiplication by CPU
    #~ noutput = numpy.dot(matrix1,matrix2).ravel()
    #~ 
    #~ # Compute the CPU time and speedup from GPU
    #~ cputime = time.time() - t
    #~ print "cpu time: {0:8.2f}ms".format(cputime * 1000)
    #~ print "speedup: {0:.2f}".format(cputime/gputime)
#~ 
    #~ # Check for errors
    #~ failed = False
    #~ for i,tup in enumerate( zip(list(noutput),list(output)) ):
	#~ cpu,gpu = tup
	#~ if abs(cpu - gpu) > FLOATING_POINT_MARGIN_OF_ERROR:
	    #~ failed = True
	    #~ print "Warning: %.3f CPU != %.3f GPU @ %d" % (cpu,gpu,i)
    #~ if not failed:
	#~ print "All tests passed! All cells agree within {0}.".format(FLOATING_POINT_MARGIN_OF_ERROR)
#~ else:
    #~ print "Not computing the multiplication on the CPU."
