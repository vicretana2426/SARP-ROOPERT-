"""Just a place to run stuff, currently has some test code
usefull as it has a bunch of commonly used import statements
CURRENT CONFIGURATION: FIRST ORDER SIZINGS FOR MID AUTUMN 2022"""
import sys
sys.path.insert(1,"./")
import scipy.optimize
#from Components.ThrustChamber import ThrustChamber
from rocketcea.cea_obj import add_new_fuel, add_new_oxidizer, add_new_propellant
import numpy as np
import math
import Components.ThrustChamber as ThrustChamber
import Components.CoolingSystem as CS
from rocketcea.cea_obj_w_units import CEA_Obj
import Toolbox.RListGenerator as RListGenerator
import Toolbox.RocketCEAAssister as RA
import os
import Toolbox.IsentropicEquations as IE
import Toolbox.RocketEquation as RE
import difflib
import re as regex
from rocketprops.rocket_prop import get_prop
import Toolbox.Constant as const
import DetermineOptimalMR as DOMR
import matplotlib.pyplot as plt
import FirstOrderCalcs as FAC
import Components.ThrustChamber as ThrustChamber
import Components.StructuralApproximation as SA
from scipy.optimize import minimize_scalar
from Toolbox import PressureDropCalculator as PD
def fixedRSquareChanelSetup(params,xlist, rlist,chlist,chanelToLandRatio,twlist,nlist,helicitylist = None,dxlist = None):# MAKE SURE TO PASS SHIT  ALREADY FLIPPED
    if helicitylist is None:
        helicitylist = np.ones(np.size(xlist))*math.pi/2
    if dxlist is None:
        dxlist=np.ones(np.size(xlist))
        index = 1
        while index<np.size(xlist):
            dxlist[index]=abs(xlist[index-1]-xlist[index])
            index = index+1
        dxlist[0]=dxlist[1] # this is shit, but I actuall calculate an extra spatial step at the start for some reason, so our CC is 1 dx too long. Makes the graphs easier to work with tho lol, off by one error be damned

    #FOR NOW THIS IS ASSUMING SQUARE CHANELS!
    #\     \  pavail\     \ 
    # \     \ |----| \     \
    #  \     \        \     \
    #   \     \        \     \
    # sin(helicitylist) pretty much makes sure that we are using the paralax angle to define the landwidth
    perimavailable = math.pi*2*(rlist+twlist)/nlist*np.sin(helicitylist)
    landwidthlist=perimavailable/(chanelToLandRatio+1)
    cwlist=perimavailable-landwidthlist

    alistflipped=chlist*cwlist
    salistflipped=cwlist/dxlist
    vlistflipped = params['mdot_fuel'] / params['rho_fuel'] / alistflipped / nlist
    #if np.min(cwlist/chlist)>10:
    #    raise Exception(f"Aspect Ratio is crazyyyyy")

    hydraulicdiamlist=4*alistflipped/(2*chlist+2*cwlist)
    coolingfactorlist = np.ones(xlist.size)
    heatingfactorlist = np.ones(xlist.size)*.6 # .6 is from cfd last year, i think its bs but whatever
    """Fin cooling factor func is 2*nf*CH+CW. nf is calculated as tanh(mL)/ml. Ml is calculated as sqrt(hpL^2/ka),
    h=hc, P=perimeter in contact with coolant = dx, A = dx*landwidth/2 (assuming only half the fin works on the coolant, 2* factor in other spot,
    I think I can do that because of axisymmetric type), k=kw, L=height of fin = chanel height
    This is all from "A Heat Transfer Textbook, around page 166 and onwards."""
    fincoolingfactorfunc = lambda hc,kw,ind : (math.tanh(chlist[ind]*math.sqrt(2*hc/kw*landwidthlist[ind]))/\
            (chlist[ind]*math.sqrt(2*hc/kw*landwidthlist[ind])))*2*chlist[ind] + cwlist[ind]

    return alistflipped, nlist, coolingfactorlist, heatingfactorlist, xlist, vlistflipped, twlist, hydraulicdiamlist, salistflipped, dxlist, fincoolingfactorfunc, cwlist

def RunCoolingSystem(chlist,
twlist,
nlist,
helicitylist,
params,
xlist,
rlist,
chanelToLandRatio, 
TC ):

    machlist,preslist,templist = TC.flowSimple(params)
    alistflipped, nlist, coolingfactorlist, heatingfactorlist, xlist, vlistflipped, twlistflipped,\
     hydraulicdiamlist, salistflipped, dxlist, fincoolingfactorfunc, cwlist   = fixedRSquareChanelSetup(params = params,
                                        xlist = np.flip(xlist), rlist = np.flip(rlist),chlist = chlist ,
                                        chanelToLandRatio = chanelToLandRatio ,twlist = twlist ,nlist = nlist,
                                        helicitylist=helicitylist)

    Twglist, hglist, Qdotlist, Twclist, hclist, Tclist, coolantpressurelist, qdotlist, fincoolingfactorlist, rholist, viscositylist, Relist = CS.steadyStateTemperatures(
        None, TC, params, salistflipped, nlist, coolingfactorlist,
        heatingfactorlist, xlist, vlistflipped, 293, params['pc'] + params['pc']*.2 + 50*const.psiToPa, twlistflipped, hydraulicdiamlist, rgaslist = rlist, fincoolingfactorfunc=fincoolingfactorfunc, dxlist = dxlist)

    material = "inconel 715"
    Structure = CS.StructuralAnalysis(rlist, xlist, nlist, chlist, cwlist, twlist, material)
    FOSlist = Structure.FOS(Twglist,Twclist,coolantpressurelist,preslist)
    xlist=np.flip(xlist) #idk whats flipping this haha but its something in the steadystatetemps function, so we have to flip it back
    return alistflipped, xlist, vlistflipped,\
     hydraulicdiamlist, salistflipped, dxlist, fincoolingfactorfunc, cwlist,\
        Twglist, hglist, Qdotlist, Twclist, hclist, Tclist, coolantpressurelist, qdotlist, fincoolingfactorlist, rholist, viscositylist, Relist,\
            FOSlist

args = {
        'thrust': 4500 * const.lbToN,  # Newtons
        'time': 33.5,  # s
        # 'rho_ox' : 1141, #Kg/M^3
        # 'rho_fuel' : 842,
        'pc': 300 * const.psiToPa,
        'pe': 10 * const.psiToPa,
       # 'phi':1,
        'cr': None,
        'lstar': 1.24,
        'fuelname': 'Ethanol_75',
        'oxname': 'N2O',
        'throat_radius_curvature': .0254 *2,
        'dp': 150 * const.psiToPa,
        'impulseguess' :  495555.24828424345,
        'rc' : .11,
        'thetac' : (35*math.pi/180),
        'isp_efficiency' : .9} #623919}
configtitle = "NitroEthanol75 2_22_23 ParamFreeze"
output=False


# FIRST DETERMINE INITIAL ESTIMATES FOR IDEAL PARAMS
path=os.path.join( "Configs",configtitle)
if output:
    os.makedirs(path,exist_ok=False)
ispmaxavg, mrideal, phiideal, ispmaxeq, ispmaxfrozen = DOMR.optimalMr(args, plot=output)
if output:
    plt.savefig(os.path.join(path, "idealisp.png"))
print(f"isp max = {ispmaxavg}, ideal mr is {mrideal}")
args['rm']=mrideal
params = FAC.SpreadsheetSolver(args)

# get pressure drop



dt=.025

#params['thrust'] = totalmass*thrusttoweight_approx*9.81 #recompute with a resonable thrust
params = FAC.SpreadsheetSolver(args)
miapprox,lambdainit,totalmass, wstruct, newheight, heightox, heightfuel, vol_ox, vol_fuel, P_tank  = SA.mass_approx(params['pc'],params['dp'], 12, params['rho_fuel'],params['rho_ox'], params['thrust'], params['isp'], params['time'], params['rm'])
L, hlist, vlist, thrustlist, isplist, machlist =\
    RE.rocketEquationCEA(params, mi = miapprox, thrust = params['thrust'], burntime = params['time'],\
         L = None, H = None, dt=dt, Af=None, ispcorrection = None)
newargs = {
    'thrust': params['thrust'],  # Newtons
    'time': params['time'],  # s
    'pc': params['pc'],
    'pe': params['pe'],
    'rm' : params['rm'],
    'rc': params['rc'],
    'lstar': params['lstar'],
    'fuelname': params['fuelname'],
    'oxname': params['oxname'],
    'throat_radius_curvature': params['throat_radius_curvature'],
    'dp': params['dp'],
    'isp_efficiency' : params['isp_efficiency']}
params = FAC.SpreadsheetSolver(newargs)
# now do it again with cr instead of rc to get all the specific values for finite combustors
newargs = {
    'thrust': params['thrust'],  # Newtons
    'time': params['time'],  # s
    'pc': params['pc'],
    'pe': params['pe'],
    'rm' : params['rm'],
    'cr': params['cr'],
    'lstar': params['lstar'],
    'fuelname': params['fuelname'],
    'oxname': params['oxname'],
    'throat_radius_curvature': params['throat_radius_curvature'],
    'dp': params['dp'],
    'isp_efficiency' : params['isp_efficiency']}
params_full = FAC.SpreadsheetSolver(newargs)

if output:
    with open(os.path.join(path, "mass_output.txt"), "w") as f:
        print(f"This is supposed to be a CSV! Eventually it should be passed params and get all that data too!", file=f)
            #overwriting current file
mis, lambdas, totalmasses, wstruct, newheight, heightox, heightfuel, vol_ox, vol_fuel, P_tank = \
    SA.mass_approx(params['pc'], params['dp'], 12, params['rho_fuel'], params['rho_ox'],
                                                params['thrust'], params['isp'], params['time'], params['rm'],
                printoutput=output, outputdir=path)
if output:
    with open(os.path.join(path, "mass_output.txt"), "a") as f:
        for param in list(params):
            if params[param] is None:
                print(param + f", NONE", file=f)
            else:
                #try:
                #    print(param + f", " +'%.3f'%(params[param]), file=f)
                #except:
                print(param + f", {params[param]}", file=f)
        print(f"Deltav, {params['isp']*9.81*math.log(1/L)}", file=f)

    title = f"Fuel = {params['fuelname']}, " \
            f"Ox = {params['oxname']}, " \
            f"mi = {int(((1 / lambdas) * params['mdot'] * params['time'] - params['mdot'] * params['time']))}," \
            f" mp = {int(params['mdot'] * params['time'])}, " \
            f"Mtotal = {int((1 / lambdas) * params['mdot'] * params['time'])}"
    RE.ShitPlotter(hlist, vlist, thrustlist, isplist, machlist, time=params['time'], title=title, dt=dt)
    plt.savefig(os.path.join(path, "trajectory.png"))
### Now that we have the "optimal rocket", figure out flow and wall temps

#conevol = math.pi*params['rc']**3*math.tan(params['thetac'])/3 - math.pi*params['rt']**3*math.tan(params['thetac'])/3
if params_full['thetac'] is None:
    params_full['thetac'] = math.pi*35/180
volfunc = lambda lc : math.pi*params_full['rc']**2*lc  +\
    math.pi*params_full['rc']**3/math.tan(params_full['thetac'])/3 -\
        math.pi*params_full['rt']**3/math.tan(params_full['thetac'])/3
lstarminimizer = lambda lc : volfunc(lc)/(params_full['rt']**2*math.pi) - params_full['lstar']
result = scipy.optimize.root(lstarminimizer, .05, args=(), method='hybr', jac=None, tol=None, callback=None, options=None)
params_full['lc']=result['x'][0]
xlist = np.linspace(0, params_full['lc'] + (params_full['rc'] - params_full['rt']) / math.tan(params_full['thetac']) + params_full['ln_conical'], 100)
    
rlist_full,xlist_full = RListGenerator.paraRlist(xlist, params_full['lc'], params_full['rc'],
                                params_full['lc'] + (params_full['rc'] - params_full['rt'])/(math.tan(params_full['thetac'])),
                                params_full['rt'],
                                params_full['lc'] + (params_full['rc'] - params_full['rt'])/(math.tan(params_full['thetac'])) + params_full['ln_conical'],
                                params_full['re'], params_full['lc']*1.8, 2*.0254, 2*.0254, math.pi/6, 8*math.pi/180, params_full['er'])  # xlist, xns, rc, xt, rt, xe, re
# xlist, xns, rc, xt, rt_sharp, xe_cone, re_cone, rcf, rtaf, rtef, thetai, thetae, ar

TC_full = ThrustChamber.ThrustChamber(rlist_full,xlist_full)
print(TC_full.rt, TC_full.xt, TC_full.xns)

machlist_full,preslist_full,templist_full = TC_full.flowSimple(params_full)
xlistflipped_full = np.flip(xlist_full)
rlistflipped_full  = np.flip(rlist_full)
chlist_full  = (TC_full.rt/rlistflipped_full)**.5*.003 
twlist_full  = (rlistflipped_full/TC_full.rt)*.001 
nlist_full  = np.ones(len(xlist_full))*80
ewlist_full  = np.ones(len(xlist_full))*.005
#HELICITY IS DEFINED AS 90 DEGREES BEING A STAIGHT CHANEL, 0 DEGREES BEING COMPLETILY CIRCUMFRNEITAL
helicitylist_full  = (rlistflipped_full**1.5/TC_full.rt**1.5)*45*math.pi/180
chanelToLandRatio_full = 2
for index in range(0,np.size(helicitylist_full )):
    if helicitylist_full [index]>math.pi/2:
        helicitylist_full [index] = math.pi/2

alistflipped_full, xlist_full, vlistflipped_full,\
    hydraulicdiamlist_full, salistflipped_full, dxlist_full, fincoolingfactorfunc_full, cwlist_full,\
        Twglist_full, hglist_full, Qdotlist_full, Twclist_full, hclist_full, Tclist_full,\
coolantpressurelist_full, qdotlist_full, fincoolingfactorlist_full, rholist_full, viscositylist_full, Relist_full, FOSlist_full = RunCoolingSystem(chlist_full,
twlist_full,
nlist_full,
helicitylist_full,
params_full,
xlist_full,
rlist_full,
chanelToLandRatio_full, 
TC_full )



## now subscale


args = {
        'thrust': 1200 * const.lbToN,  # Newtons
        'time': 7.5,  # s
        # 'rho_ox' : 1141, #Kg/M^3
        # 'rho_fuel' : 842,
        'pc': 300 * const.psiToPa,
        'pe': 10 * const.psiToPa,
       # 'phi':1,
        'cr': 5.295390217,
        'lstar': 1.24,
        'fuelname': 'Ethanol_75',
        'oxname': 'N2O',
        'throat_radius_curvature': .0254 *2,
        'dp': 150 * const.psiToPa,
        'impulseguess' :  495555.24828424345,
        #'rc' : .11,
        'thetac' : (35*math.pi/180),
        'isp_efficiency' : .9} #623919}
configtitle = "Subscale 3_7_23"
output=False


# FIRST DETERMINE INITIAL ESTIMATES FOR IDEAL PARAMS
path=os.path.join( "Configs",configtitle)
if output:
    os.makedirs(path,exist_ok=True)
ispmaxavg, mrideal, phiideal, ispmaxeq, ispmaxfrozen = DOMR.optimalMr(args, plot=output)
if output:
    plt.savefig(os.path.join(path, "idealisp.png"))
print(f"isp max = {ispmaxavg}, ideal mr is {mrideal}")
args['rm']=mrideal
params = FAC.SpreadsheetSolver(args)

# get pressure drop



dt=.025

#params['thrust'] = totalmass*thrusttoweight_approx*9.81 #recompute with a resonable thrust
params = FAC.SpreadsheetSolver(args)
miapprox,lambdainit,totalmass, wstruct, newheight, heightox, heightfuel, vol_ox, vol_fuel, P_tank  = SA.mass_approx(params['pc'],params['dp'], 12, params['rho_fuel'],params['rho_ox'], params['thrust'], params['isp'], params['time'], params['rm'])
L, hlist, vlist, thrustlist, isplist, machlist =\
    RE.rocketEquationCEA(params, mi = miapprox, thrust = params['thrust'], burntime = params['time'],\
         L = None, H = None, dt=dt, Af=None, ispcorrection = None)
newargs = {
    'thrust': params['thrust'],  # Newtons
    'time': params['time'],  # s
    'pc': params['pc'],
    'pe': params['pe'],
    'rm' : params['rm'],
    'rc': params['rc'],
    'lstar': params['lstar'],
    'fuelname': params['fuelname'],
    'oxname': params['oxname'],
    'throat_radius_curvature': params['throat_radius_curvature'],
    'dp': params['dp'],
    'isp_efficiency' : params['isp_efficiency']}
params = FAC.SpreadsheetSolver(newargs)
# now do it again with cr instead of rc to get all the specific values for finite combustors
newargs = {
    'thrust': params['thrust'],  # Newtons
    'time': params['time'],  # s
    'pc': params['pc'],
    'pe': params['pe'],
    'rm' : params['rm'],
    'cr': params['cr'],
    'lstar': params['lstar'],
    'fuelname': params['fuelname'],
    'oxname': params['oxname'],
    'throat_radius_curvature': params['throat_radius_curvature'],
    'dp': params['dp'],
    'isp_efficiency' : params['isp_efficiency']}
params = FAC.SpreadsheetSolver(newargs)

if output:
    with open(os.path.join(path, "mass_output.txt"), "w") as f:
        print(f"This is supposed to be a CSV! Eventually it should be passed params and get all that data too!", file=f)
            #overwriting current file
mis, lambdas, totalmasses, wstruct, newheight, heightox, heightfuel, vol_ox, vol_fuel, P_tank = \
    SA.mass_approx(params['pc'], params['dp'], 12, params['rho_fuel'], params['rho_ox'],
                                                params['thrust'], params['isp'], params['time'], params['rm'],
                printoutput=output, outputdir=path)
if output:
    with open(os.path.join(path, "mass_output.txt"), "a") as f:
        for param in list(params):
            if params[param] is None:
                print(param + f", NONE", file=f)
            else:
                #try:
                #    print(param + f", " +'%.3f'%(params[param]), file=f)
                #except:
                print(param + f", {params[param]}", file=f)
        print(f"Deltav, {params['isp']*9.81*math.log(1/L)}", file=f)

    title = f"Fuel = {params['fuelname']}, " \
            f"Ox = {params['oxname']}, " \
            f"mi = {int(((1 / lambdas) * params['mdot'] * params['time'] - params['mdot'] * params['time']))}," \
            f" mp = {int(params['mdot'] * params['time'])}, " \
            f"Mtotal = {int((1 / lambdas) * params['mdot'] * params['time'])}"
    RE.ShitPlotter(hlist, vlist, thrustlist, isplist, machlist, time=params['time'], title=title, dt=dt)
    plt.savefig(os.path.join(path, "trajectory.png"))
### Now that we have the "optimal rocket", figure out flow and wall temps

#conevol = math.pi*params['rc']**3*math.tan(params['thetac'])/3 - math.pi*params['rt']**3*math.tan(params['thetac'])/3
if params['thetac'] is None:
    params['thetac'] = math.pi*35/180
volfunc = lambda lc : math.pi*params['rc']**2*lc  +\
    math.pi*params['rc']**3/math.tan(params['thetac'])/3 -\
        math.pi*params['rt']**3/math.tan(params['thetac'])/3
lstarminimizer = lambda lc : volfunc(lc)/(params['rt']**2*math.pi) - params['lstar']
result = scipy.optimize.root(lstarminimizer, .05, args=(), method='hybr', jac=None, tol=None, callback=None, options=None)
params['lc']=result['x'][0]
xlist = np.linspace(0, params['lc'] + (params['rc'] - params['rt']) / math.tan(params['thetac']) + params['ln_conical'], 100)
    
rlist,xlist = RListGenerator.paraRlist(xlist, params['lc'], params['rc'],
                                params['lc'] + (params['rc'] - params['rt'])/(math.tan(params['thetac'])),
                                params['rt'],
                                params['lc'] + (params['rc'] - params['rt'])/(math.tan(params['thetac'])) + params['ln_conical'],
                                params['re'], params['lc']*.5, .0254, .0254, math.pi/6, 8*math.pi/180, params['er'])  # xlist, xns, rc, xt, rt, xe, re
# xlist, xns, rc, xt, rt_sharp, xe_cone, re_cone, rcf, rtaf, rtef, thetai, thetae, ar

TC = ThrustChamber.ThrustChamber(rlist,xlist)
print(TC.rt, TC.xt, TC.xns)

machlist,preslist,templist = TC.flowSimple(params)
xlistflipped = np.flip(xlist)
rlistflipped  = np.flip(rlist)
chlist  = (TC.rt/rlistflipped)**.5*.003 
twlist  = (rlistflipped/TC.rt)*.001 
nlist  = np.ones(len(xlist))*21
ewlist  = np.ones(len(xlist))*.005
#HELICITY IS DEFINED AS 90 DEGREES BEING A STAIGHT CHANEL, 0 DEGREES BEING COMPLETILY CIRCUMFRNEITAL
helicitylist  = (rlistflipped**1.5/TC.rt**1.5)*45*math.pi/180
#chanelToLandRatio = 2



for index in range(0,np.size(helicitylist )):
    if helicitylist [index]>math.pi/2:
        helicitylist [index] = math.pi/2

perimavailable = math.pi*2*(np.flip(rlist)+twlist)/nlist*np.sin(helicitylist)

chanelToLandRatio=1/(1-min(cwlist_full)/min(perimavailable))-1#
alistflipped, xlist, vlistflipped,\
    hydraulicdiamlist, salistflipped, dxlist, fincoolingfactorfunc, cwlist,\
        Twglist, hglist, Qdotlist, Twclist, hclist, Tclist, coolantpressurelist, qdotlist, fincoolingfactorlist, rholist, viscositylist, Relist, FOSlist = RunCoolingSystem(chlist,
twlist,
nlist,
helicitylist,
params,
xlist,
rlist,
chanelToLandRatio, 
TC )

plt.figure()
plt.plot(np.hstack((np.flip(xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) ,label=f"subscale")
plt.plot(np.hstack((np.flip(xlist_full),xlist_full)),np.hstack((np.flip(rlist_full),-rlist_full)) ,label=f"fullscale")
plt.grid()
plt.legend()
plt.title("geom comparison")



title=f"Chamber Wall Temperatures"
plt.figure()
plt.plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp, K, sub")
plt.plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp, K, sub") # row=0, column=0
plt.plot(xlistflipped,Tclist , 'b', label="Coolant Temp, K, sub") # 
plt.plot(xlistflipped_full,Twglist_full , 'g--', label="Gas Side Wall Temp, K, full")
plt.plot(xlistflipped_full,Twclist_full , 'r--', label="CoolantSide Wall Temp, K, full") # row=0, column=0
plt.plot(xlistflipped_full,Tclist_full , 'b--', label="Coolant Temp, K, full") # 
plt.xlabel("Axial Position [m From Injector Face]")
plt.ylabel("Temperature [K]")
plt.legend()
plt.title(title)


tilte = f"Chanel Geoms"
plt.figure()
plt.plot(xlistflipped,chlist*1000,'r',label="Chanel Height [mm]")
plt.plot(xlistflipped,cwlist*1000,'b',label="Chanel Width [mm]")
plt.plot(xlistflipped,twlist*1000,'k',label="Wall Thickness [mm]")
plt.plot(xlistflipped,hydraulicdiamlist*1000,'g',label="Hydraulic Diam [mm]")
plt.plot(xlistflipped,helicitylist*180/math.pi/10,'m',label="helicity [10's of degrees]")
plt.plot(xlistflipped,vlistflipped,'c',label="Coolant Velocity [m/s]")

plt.plot(xlistflipped_full,chlist_full*1000,'r--',label="Chanel Height [mm] _full")
plt.plot(xlistflipped_full,cwlist_full*1000,'b--',label="Chanel Width [mm] _full")
plt.plot(xlistflipped_full,twlist_full*1000,'k--',label="Wall Thickness [mm] _full")
plt.plot(xlistflipped_full,hydraulicdiamlist_full*1000,'g--',label="Hydraulic Diam [mm] _full")
plt.plot(xlistflipped_full,helicitylist_full*180/math.pi/10,'m--',label="helicity [10's of degrees] _full")
plt.plot(xlistflipped_full,vlistflipped_full,'c--',label="Coolant Velocity [m/s] _full")
plt.legend()
plt.xlabel("TC position, meters")
plt.ylabel("Thicknesses, [mm]")
plt.title(f"Geometry , nsub = {int(nlist[1])}, Chanel to Landsub = {chanelToLandRatio},  nfull = {int(nlist_full[1])}, Chanel to Land full = {chanelToLandRatio_full}")


title="ChamberTemps"
fig, axs = plt.subplots(3,3)
fig.suptitle(title)

axs[0,1].plot(xlistflipped,hglist , 'g')  # row=0, column=0
axs[1,1].plot(xlistflipped,hclist , 'r')# row=1, column=0
axs[2,1].plot(np.hstack((np.flip(TC.xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) , 'k') # row=0, column=0


axs[0,1].set_title('hglist')
axs[1,1].set_title('hclist')
axs[2,1].set_title('Thrust Chamber Shape')

axs[0,0].plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp")
axs[0,0].plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp") # row=0, column=0
axs[0,0].plot(xlistflipped,Tclist , 'b', label="Coolant Temp") #
axs[1,0].plot(xlistflipped,Tclist , 'r')# row=1, column=0
axs[2,0].plot(xlistflipped,hydraulicdiamlist , 'r')# row=1, column=0

axs[0,0].set_title('Twg')
axs[1,0].set_title('Tc')
axs[2,0].set_title('hydraulicdiam')
axs[0,0].legend()

axs[0,2].plot(xlistflipped,Twglist*const.degKtoR-458.67 , 'g', label="Gas Side Wall Temp, F")
#axs[0,2].plot(xlistflipped,Tcoatinglist*const.degKtoR-458.67 , 'k', label="Opposite side of coating Temp, F")
axs[0,2].plot(xlistflipped,Twclist * const.degKtoR-458.67, 'r', label="CoolantSide Wall Temp, F") # row=0, column=0

axs[0,2].plot(xlistflipped,Tclist * const.degKtoR-458.67, 'b', label="Coolant Temp, F") #
axs[1,2].plot(xlistflipped,coolantpressurelist /const.psiToPa, 'k')
axs[2,2].plot(xlistflipped,rholist, 'k') # row=0, column=0

axs[0,2].set_title('Twg')
axs[1,2].set_title('coolantpressure (psi)')
axs[2,2].set_title('density of coolant')
axs[0,2].legend()

axs[0,1].plot(xlistflipped_full,hglist_full , 'g--')  # row=0, column=0
axs[1,1].plot(xlistflipped_full,hclist_full , 'r--')# row=1, column=0
axs[2,1].plot(np.hstack((np.flip(TC_full.xlist),xlist_full)),np.hstack((np.flip(rlist_full),-rlist_full)) , 'k') # row=0, column=0


axs[0,1].set_title('hglist')
axs[1,1].set_title('hclist')
axs[2,1].set_title('Thrust Chamber Shape')

axs[0,0].plot(xlistflipped_full,Twglist_full , 'g--', label="Gas Side Wall Temp")
axs[0,0].plot(xlistflipped_full,Twclist_full , 'r--', label="CoolantSide Wall Temp") # row=0, column=0
axs[0,0].plot(xlistflipped_full,Tclist_full , 'b--', label="Coolant Temp") #
axs[1,0].plot(xlistflipped_full,Tclist_full , 'r--')# row=1, column=0
axs[2,0].plot(xlistflipped_full,hydraulicdiamlist_full , 'r--')# row=1, column=0

axs[0,0].set_title('Twg')
axs[1,0].set_title('Tc')
axs[2,0].set_title('hydraulicdiam')
axs[0,0].legend()

axs[0,2].plot(xlistflipped_full,Twglist_full*const.degKtoR-458.67 , 'g--', label="Gas Side Wall Temp, F")
#axs[0,2].plot(xlistflipped_full,Tcoatinglist*const.degKtoR-458.67 , 'k--', label="Opposite side of coating Temp, F")
axs[0,2].plot(xlistflipped_full,Twclist_full * const.degKtoR-458.67, 'r--', label="CoolantSide Wall Temp, F") # row=0, column=0

axs[0,2].plot(xlistflipped_full,Tclist_full * const.degKtoR-458.67, 'b--', label="Coolant Temp, F") #
axs[1,2].plot(xlistflipped_full,coolantpressurelist_full /const.psiToPa, 'k--')
axs[2,2].plot(xlistflipped_full,rholist_full, 'k--') # row=0, column=0

axs[0,2].set_title('Twg')
axs[1,2].set_title('coolantpressure (psi)')
axs[2,2].set_title('density of coolant')
axs[0,2].legend()


title=f"Heat Flow Comparison per unit length per chanel"
plt.figure()
plt.plot(xlistflipped,Qdotlist , 'g', label="Heat flow per unit length, sub")
plt.plot(xlistflipped_full,Qdotlist_full , 'g--', label="Heat flow per unit length, full")
plt.xlabel("Axial Position [m From Injector Face]")
plt.ylabel("Qdot  [w/m]")
plt.legend()
plt.title(title)

title=f"Heat Flow Comparison per unit area"
plt.figure()
plt.plot(xlistflipped,qdotlist , 'g', label="Heat flow , sub")
plt.plot(xlistflipped_full,qdotlist_full , 'g--', label="Heat flow, full")
plt.xlabel("Axial Position [m From Injector Face]")
plt.ylabel("qdot  [w/m^2]")
plt.legend()
plt.title(title)

title=f"FOS"
plt.figure()
plt.plot(xlistflipped,FOSlist , 'b', label="Factor of Safety , sub")
plt.plot(xlistflipped_full,FOSlist_full , 'b--', label="Factor of Safety, full")
plt.xlabel("Axial Position [m From Injector Face]")
plt.ylabel("Factor of Safety")
plt.legend()
plt.title(title)

plt.show()


if output:
    #Twglist, hglist, qdotlist, Twclist, hclist, Tclist, coolantpressurelist, qdotlist, Trlist, rholist, viscositylist, Relist = CS.steadyStateTemperatures(None,TC, params, salistflipped,n, coolingfactorlist,
    #                        heatingfactorlist, xlistflipped, vlistflipped ,293, params['pc']+params['dp'][0], twlistflipped, hydraulicdiamlist)

    title="ChamberTemps"
    fig, axs = plt.subplots(3,3)
    fig.suptitle(title)

    axs[0,1].plot(xlistflipped,hglist , 'g')  # row=0, column=0
    axs[1,1].plot(xlistflipped,hclist , 'r')# row=1, column=0
    axs[2,1].plot(np.hstack((np.flip(TC.xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) , 'k') # row=0, column=0


    axs[0,1].set_title('hglist')
    axs[1,1].set_title('hclist')
    axs[2,1].set_title('Thrust Chamber Shape')

    axs[0,0].plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp")
    axs[0,0].plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp") # row=0, column=0
    axs[0,0].plot(xlistflipped,Tclist , 'b', label="Coolant Temp") #
    axs[1,0].plot(xlistflipped,Tclist , 'r')# row=1, column=0
    axs[2,0].plot(xlistflipped,hydraulicdiamlist , 'r')# row=1, column=0

    axs[0,0].set_title('Twg')
    axs[1,0].set_title('Tc')
    axs[2,0].set_title('hydraulicdiam')
    axs[0,0].legend()

    axs[0,2].plot(xlistflipped,Twglist*const.degKtoR-458.67 , 'g', label="Gas Side Wall Temp, F")
    #axs[0,2].plot(xlistflipped,Tcoatinglist*const.degKtoR-458.67 , 'k', label="Opposite side of coating Temp, F")
    axs[0,2].plot(xlistflipped,Twclist * const.degKtoR-458.67, 'r', label="CoolantSide Wall Temp, F") # row=0, column=0

    axs[0,2].plot(xlistflipped,Tclist * const.degKtoR-458.67, 'b', label="Coolant Temp, F") #
    axs[1,2].plot(xlistflipped,coolantpressurelist /const.psiToPa, 'k')
    axs[2,2].plot(xlistflipped,rholist, 'k') # row=0, column=0

    axs[0,2].set_title('Twg')
    axs[1,2].set_title('coolantpressure (psi)')
    axs[2,2].set_title('density of coolant')
    axs[0,2].legend()
    #plt.savefig(os.path.join(path, "temperatures.png"))
    print(f"max twg = {np.max(Twglist)} in kelvin, {np.max(Twglist)*const.degKtoR} in Rankine (freedom)\n max Twc ="
            f" {np.max(Twclist)} in kelvin, {np.max(Twclist)*const.degKtoR} in Rankine (freedom)")
    # Hide x labels and tick labels for top plots and y ticks for right plots.

    title="Flow properties along thrust chamber"
    fig1, axs1 = plt.subplots(4,1)

    fig1.suptitle(title)

    axs1[0].plot(TC.xlist,machlist , 'g')  # row=0, column=0
    axs1[1].plot(TC.xlist,preslist , 'r')# row=1, column=0
    axs1[2].plot(TC.xlist,templist , 'b') # row=0, column=0
    axs1[3].plot(np.hstack((np.flip(TC.xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) , 'k') # row=0, column=0


    axs1[0].set_title('Mach')
    axs1[1].set_title('Pressure')
    axs1[2].set_title('temperature')
    #plt.savefig(os.path.join(path, "flowprops.png"))

    title=f"Chamber Wall Temperatures: Temp At Injector Face = {Twglist[-1]}"
    plt.figure()
    plt.plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp, K")
    plt.plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp, K") # row=0, column=0
    plt.plot(xlistflipped,Tclist , 'b', label="Coolant Temp, K") # 
    plt.xlabel("Axial Position [m From Injector Face]")
    plt.ylabel("Temperature [K]")
    plt.legend()
    plt.title(title)
    plt.savefig(os.path.join(path, "ChamberTemps_LachlanFormat.png"))

    axs[0,1].plot(xlistflipped,hglist , 'g')  # row=0, column=0
    axs[1,1].plot(xlistflipped,hclist , 'r')# row=1, column=0
    axs[2,1].plot(np.hstack((np.flip(TC.xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) , 'k') # row=0, column=0


    axs[0,1].set_title('hglist')
    axs[1,1].set_title('hclist')
    axs[2,1].set_title('Thrust Chamber Shape')

    axs[0,0].plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp")
    axs[0,0].plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp") # row=0, column=0
    axs[0,0].plot(xlistflipped,Tclist , 'b', label="Coolant Temp") #
    axs[1,0].plot(xlistflipped,Tclist , 'r')# row=1, column=0
    axs[2,0].plot(xlistflipped,hydraulicdiamlist , 'r')# row=1, column=0

    axs[0,0].set_title('Twg')
    axs[1,0].set_title('Tc')
    axs[2,0].set_title('hydraulicdiam')
    axs[0,0].legend()

    axs[0,2].plot(xlistflipped,Twglist*const.degKtoR-458.67 , 'g', label="Gas Side Wall Temp, F")
    #axs[0,2].plot(xlistflipped,Tcoatinglist*const.degKtoR-458.67 , 'k', label="Opposite side of coating Temp, F")
    axs[0,2].plot(xlistflipped,Twclist * const.degKtoR-458.67, 'r', label="CoolantSide Wall Temp, F") # row=0, column=0

    axs[0,2].plot(xlistflipped,Tclist * const.degKtoR-458.67, 'b', label="Coolant Temp, F") #
    axs[1,2].plot(xlistflipped,coolantpressurelist /const.psiToPa, 'k')
    axs[2,2].plot(xlistflipped,rholist, 'k') # row=0, column=0

    axs[0,2].set_title('Twg')
    axs[1,2].set_title('coolantpressure (psi)')
    axs[2,2].set_title('density of coolant')
    axs[0,2].legend()
    #plt.savefig(os.path.join(path, "temperatures.png"))
    print(f"max twg = {np.max(Twglist)} in kelvin, {np.max(Twglist)*const.degKtoR} in Rankine (freedom)\n max Twc ="
            f" {np.max(Twclist)} in kelvin, {np.max(Twclist)*const.degKtoR} in Rankine (freedom)")


    title=f"Chamber Wall Temperatures: Temp At Injector Face = {Twglist[-1]}"
    plt.figure()
    plt.plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp, K")
    plt.plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp, K") # row=0, column=0
    plt.plot(xlistflipped,Tclist , 'b', label="Coolant Temp, K") # 
    plt.xlabel("Axial Position [m From Injector Face]")
    plt.ylabel("Wall Temperature [K]")
    plt.title(title)
    plt.savefig(os.path.join(path, "ChamberTemps_LachlanFormat.png"))

    axs[0,1].plot(xlistflipped,hglist , 'g')  # row=0, column=0
    axs[1,1].plot(xlistflipped,hclist , 'r')# row=1, column=0
    axs[2,1].plot(np.hstack((np.flip(TC.xlist),xlist)),np.hstack((np.flip(rlist),-rlist)) , 'k') # row=0, column=0


    axs[0,1].set_title('hglist')
    axs[1,1].set_title('hclist')
    axs[2,1].set_title('Thrust Chamber Shape')

    axs[0,0].plot(xlistflipped,Twglist , 'g', label="Gas Side Wall Temp")
    axs[0,0].plot(xlistflipped,Twclist , 'r', label="CoolantSide Wall Temp") # row=0, column=0
    axs[0,0].plot(xlistflipped,Tclist , 'b', label="Coolant Temp") #
    axs[1,0].plot(xlistflipped,Tclist , 'r')# row=1, column=0
    axs[2,0].plot(xlistflipped,hydraulicdiamlist , 'r')# row=1, column=0

    axs[0,0].set_title('Twg')
    axs[1,0].set_title('Tc')
    axs[2,0].set_title('hydraulicdiam')
    axs[0,0].legend()

    axs[0,2].plot(xlistflipped,Twglist*const.degKtoR-458.67 , 'g', label="Gas Side Wall Temp, F")
    #axs[0,2].plot(xlistflipped,Tcoatinglist*const.degKtoR-458.67 , 'k', label="Opposite side of coating Temp, F")
    axs[0,2].plot(xlistflipped,Twclist * const.degKtoR-458.67, 'r', label="CoolantSide Wall Temp, F") # row=0, column=0

    axs[0,2].plot(xlistflipped,Tclist * const.degKtoR-458.67, 'b', label="Coolant Temp, F") #
    axs[1,2].plot(xlistflipped,coolantpressurelist /const.psiToPa, 'k')
    axs[2,2].plot(xlistflipped,rholist, 'k') # row=0, column=0

    axs[0,2].set_title('Twg')
    axs[1,2].set_title('coolantpressure (psi)')
    axs[2,2].set_title('density of coolant')
    axs[0,2].legend()
    #plt.savefig(os.path.join(path, "temperatures.png"))
    print(f"max twg = {np.max(Twglist)} in kelvin, {np.max(Twglist)*const.degKtoR} in Rankine (freedom)\n max Twc ="
            f" {np.max(Twclist)} in kelvin, {np.max(Twclist)*const.degKtoR} in Rankine (freedom)")

    plt.show()

if ~output:
    params['mi'] = mis
    params['L'] = lambdas
    params['M'] = totalmasses
    params['wstruct'] = wstruct
    params['newheight'] = newheight
    params['heightox'] = heightox
    params['heightfuel'] = heightfuel
    params['vol_ox'] = vol_ox
    params['vol_fuel'] = vol_fuel
    params['P_tank'] = P_tank
    params['twg_max'] = np.max(Twglist)
    params['twc_max'] =  np.max(Twclist)

