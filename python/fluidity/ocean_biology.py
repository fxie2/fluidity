import fluidity_tools

def short_wave_radiation(t,deg_lon,deg_lat,cloud):
    """ Calculatate approximate value of short wave radiation
    based on latitude"""

    # This code is based on that in GOTM, which in turn is from MOM.
    # GOTM is released under GNU GPL v2. 

    import math
    from datetime import datetime, timedelta

    deg2rad=math.pi/180.
    rad2deg=180./math.pi
    solar=1350.
    eclips=23.439*deg2rad
    tau=0.7
    aozone=0.09
    yrdays = 365.

    # Constants to work out the albedo, Payne, 1972
    alb1 = [.719,.656,.603,.480,.385,.300,.250,.193,.164,
            .131,.103,.084,.071,.061,.054,.039,.036,.032,.031,.030]
    za = [90.,88.,86.,84.,82.,80.,78.,76.,74.,70.,
          66.,62.,58.,54.,50.,40.,30.,20.,10.,0.0]
    dza = [2.,2.,2.,2.,2.,2.,2.,2.,4.,4.,4.,4.,4.,4.,10.,10.,
            10.,10.,10.]

    radians_lon = deg2rad*deg_lon
    radians_lat = deg2rad*deg_lat

    # get some time units sorted
    # day of year
    days = t.timetuple().tm_yday
    hour = t.hour


    # Fractional year in radians
    th0 = 2.*math.pi*days/yrdays
    th02 = 2.*th0
    th03 = 3.*th0
    #  solar declination
    sun_dec = 0.006918 - 0.399912*math.cos(th0) + 0.070257*math.sin(th0) \
            - 0.006758*math.cos(th02) + 0.000907*math.sin(th02)          \
            - 0.002697*math.cos(th03) + 0.001480*math.sin(th03)

    # solar hour angle
    theta_sun = (hour-12.)*15.*deg2rad + radians_lon

    # cosine of the solar zenith angle
    coszen =math.sin(radians_lat)*math.sin(sun_dec)+math.cos(radians_lat)*math.cos(sun_dec)*math.cos(theta_sun)
    if (coszen < 0.0) :
      coszen = 0.0
      q_attenuation = 0.0
    else:
      q_attenuation = tau**(1./coszen)
    
    # work out the energy received due our position and datetime
    qzer  = coszen * solar
    # This is the direct energy, after taking into account attenuation effect of atmosphere
    qdir  = qzer * q_attenuation
    # Re-radiation contribution
    qdiff = ((1.-aozone)*qzer - qdir) * 0.5
    # Finally, add the direct (solar+attenuation) and the re-radiated contribution
    qtot  =  qdir + qdiff

    # declination angle
    dec = eclips*math.sin((days-81.)/yrdays*2.*math.pi)
    # sin of the solar noon altitude in radians :
    sunbet=math.sin(radians_lat)*math.sin(dec)+math.cos(radians_lat)*math.cos(dec)
    # solar noon altitude in degrees :
    sol_noon_alt = math.asin(sunbet)*rad2deg

    #  calculates the albedo as a function of the solar zenith angle :
    #  (after Payne, 1972). I have no idea what the mysterious intermediate
    # variables are.
    zen=(180./math.pi)*math.acos(coszen)
    if(zen >= 74.):
      jab=int(.5*(90.-zen))
    elif (zen >= 50.):
      jab=int(.23*(74.-zen)+8.)
    else:
      jab=int(.10*(50.-zen)+14.)
    dzen=(za[jab]-zen)/dza[jab]
    albedo=alb1[jab]+dzen*(alb1[jab+1]-alb1[jab])

    # Finally, lets get the shortwave radiation, taking into account cloud cover, 
    # albedo and our location and time.
    #  radiation as from Reed(1977), Simpson and Paulson(1979)
    #  calculates SHORT WAVE FLUX ( watt/m*m )
    #  Rosati,Miyakoda 1988 ; eq. 3.8
    qshort  = qtot*(1-0.62*cloud + .0019*sol_noon_alt)*(1.-albedo)
    if(qshort > qtot ):
      qshort  = qtot
    
    return qshort


def pznd(state, parameters):
    '''Calculate sources and sinks for a simple PZND model'''
    
    if not check_pznd_parameters(parameters):
        raise TypeError("Missing Parameter")
    
    P=state.scalar_fields["Phytoplankton"]
    Z=state.scalar_fields["Zooplankton"]
    N=state.scalar_fields["Nutrient"]
    D=state.scalar_fields["Detritus"]
    I=state.scalar_fields["_PAR"]
    Pnew=state.scalar_fields["IteratedPhytoplankton"]
    Znew=state.scalar_fields["IteratedZooplankton"]
    Nnew=state.scalar_fields["IteratedNutrient"]
    Dnew=state.scalar_fields["IteratedDetritus"]
    coords=state.vector_fields["Coordinate"]

    P_source=state.scalar_fields["PhytoplanktonSource"]
    Z_source=state.scalar_fields["ZooplanktonSource"]
    N_source=state.scalar_fields["NutrientSource"]
    D_source=state.scalar_fields["DetritusSource"]
    N_abs=state.scalar_fields["NutrientAbsorption"]
    try:
        PP=state.scalar_fields["PrimaryProduction"]
    except KeyError:
        PP=None
    try:
        PG=state.scalar_fields["PhytoplanktonGrazing"]
    except KeyError:
        PG=None
    

    alpha=parameters["alpha"]
    beta=parameters["beta"]
    gamma=parameters["gamma"]
    g=parameters["g"]
    k_N=parameters["k_N"]
    k=parameters["k"]
    v=parameters["v"]
    mu_P=parameters["mu_P"]
    mu_Z=parameters["mu_Z"]
    mu_D=parameters["mu_D"]
    p_P=parameters["p_P"]
    p_D=1-p_P


    for n in range(P.node_count):
        # Values of fields on this node.
        P_n=max(.5*(P.node_val(n)+Pnew.node_val(n)), 0.0)
        Z_n=max(.5*(Z.node_val(n)+Znew.node_val(n)), 0.0)
        N_n=max(.5*(N.node_val(n)+Nnew.node_val(n)), 0.0)
        D_n=max(.5*(D.node_val(n)+Dnew.node_val(n)), 0.0)
        I_n=max(I.node_val(n), 0.0)

        # Light limited phytoplankton growth rate.
        J=(v*alpha*I_n)/(v**2+alpha**2*I_n**2)**0.5

        # Nitrate limiting factor.
        Q=N_n/(k_N+N_n)

        # Total phytoplankton growth rate.
        R_P=J*P_n*Q

        # Zooplankton grazing of phytoplankton.
        G_P=(g * p_P * P_n**2 * Z_n)/(k**2 + p_P*P_n**2 + p_D*D_n**2)

        # Zooplankton grazing of detritus.
        G_D=(g * (1-p_P) * D_n**2 * Z_n)/(k**2 + p_P*P_n**2 + p_D*D_n**2)

        # Death rate of phytoplankton.
        De_P=mu_P*P_n*P_n/(P_n+0.2)

        # Death rate of zooplankton.
        De_Z=mu_Z*Z_n*Z_n*Z_n/(Z_n+3)

        # Detritus remineralisation.
        De_D=mu_D*D_n

        P_source.set(n, R_P - G_P - De_P)
        
        if PP:
            PP.set(n, R_P)
        if PG:
            PG.set(n, G_P)

        Z_source.set(n, gamma*beta*(G_P+G_D) - De_Z)
        
        N_source.set(n, -R_P + De_D + (1-gamma)*beta*(G_P+G_D))

        D_source.set(n, -De_D + De_P + De_Z +(1-beta)*G_P - beta*G_D)    


def check_pznd_parameters(parameters):
    from sys import stderr

    valid=True

    if not parameters.has_key("alpha"):
        stderr.write("PZND parameter alpha missing.\n")
        stderr.write("alpha is this initial slope of the P-I curve.\n\n")
        valid = False

    if not parameters.has_key("beta"):
        stderr.write("PZND parameter beta missing.\n")
        stderr.write("beta is the assimilation efficiency of zooplankton.\n\n")
        valid = False

    if not parameters.has_key("gamma"):
        stderr.write("PZND parameter gamma missing.\n")
        stderr.write("gamma is the zooplankton excretion parameter.\n\n")
        valid = False

    if not parameters.has_key("g"):
        stderr.write("PZND parameter g missing.\n")
        stderr.write("g is the zooplankton maximum growth rate.\n\n")
        valid = False

    if not parameters.has_key("k_N"):
        stderr.write("PZND parameter k_N missing.\n")
        stderr.write("k_N is the half-saturation constant for nutrient.\n\n")
        valid = False

    if not parameters.has_key("k"):
        stderr.write("PZND parameter k missing.\n")
        stderr.write("k is the zooplankton grazing parameter.\n\n")
        valid = False

    if not parameters.has_key("mu_P"):
        stderr.write("PZND parameter mu_P missing.\n")
        stderr.write("mu_P is the phytoplankton mortality rate.\n\n")
        valid = False

    if not parameters.has_key("mu_Z"):
        stderr.write("PZND parameter mu_Z missing.\n")
        stderr.write("mu_Z is the zooplankton mortality rate.\n\n")
        valid = False

    if not parameters.has_key("mu_D"):
        stderr.write("PZND parameter mu_D missing.\n")
        stderr.write("mu_D is the detritus remineralisation rate.\n\n")
        valid = False

    if not parameters.has_key("p_P"):
        stderr.write("PZND parameter p_P missing.\n")
        stderr.write("p_P is the relative grazing preference of zooplankton for phytoplankton.\n\n")
        valid = False

    if not parameters.has_key("v"):
        stderr.write("PZND parameter v missing.\n")
        stderr.write("v is the maximum phytoplankton growth rate.\n\n")
        valid = False

    return valid
    
def lotka_volterra(state,parameters):

    if not check_lotka_volterra_parameters(parameters):
        raise TypeError("Missing Parameter")
    
    P=state.scalar_fields["Phytoplankton"]
    Z=state.scalar_fields["Zooplankton"]
    Pnew=state.scalar_fields["IteratedPhytoplankton"]
    Znew=state.scalar_fields["IteratedZooplankton"]
    
    P_source=state.scalar_fields["PhytoplanktonSource"]
    Z_source=state.scalar_fields["ZooplanktonSource"]

    alpha=parameters["alpha"]
    beta=parameters["beta"]
    gamma=parameters["gamma"]
    delta=parameters["delta"]

    for n in range(P.node_count):
        # Values of fields on this node.
        P_n=.5*(P.node_val(n)+Pnew.node_val(n))
        Z_n=.5*(Z.node_val(n)+Znew.node_val(n))
    
        P_source.set(n, P_n*(alpha-beta*Z_n))

        Z_source.set(n, -Z_n*(gamma-delta*P_n))


def check_lotka_volterra_parameters(parameters):
    from sys import stderr

    valid=True

    if not parameters.has_key("alpha"):
        stderr.write("Lotka Voltera parameter alpha missing.\n")
        valid = False

    if not parameters.has_key("beta"):
        stderr.write("Lotka Voltera parameter beta missing.\n")
        valid = False

    if not parameters.has_key("gamma"):
        stderr.write("Lotka Voltera parameter gamma missing.\n")
        valid = False

    if not parameters.has_key("delta"):
        stderr.write("Lotka Voltera parameter delta missing.\n")
        valid = False

    if not valid:
        stderr.write(" dP/dt = P*(alpha-beta * Z)")
        stderr.write(" dZ/dt = - Z*(gamma-delta * P)")

    return valid

#############################################################
#                                                           #
#                      pczdna model                         #
#                                                           #
#############################################################
def six_component(state, parameters):
    '''Calculate sources and sinks for pczdna biology model'''
    

    # Based on the equations in
    # Popova, E. E.; Coward, A. C.; Nurser, G. A.; de Cuevas, B.; Fasham, M. J. R. & Anderson, T. R. 
    # Mechanisms controlling primary and new production in a global ecosystem model - Part I: 
    # Validation of the biological simulation Ocean Science, 2006, 2, 249-266. 
    # DOI: 10.5194/os-2-249-2006
    import math

    if not check_six_component_parameters(parameters):
        raise TypeError("Missing Parameter")
    
    P=state.scalar_fields["Phytoplankton"]
    C=state.scalar_fields["Chlorophyll"]
    Z=state.scalar_fields["Zooplankton"]
    N=state.scalar_fields["Nutrient"]
    A=state.scalar_fields["Ammonium"]
    D=state.scalar_fields["Detritus"]
    I=state.scalar_fields["_PAR"]
    Pnew=state.scalar_fields["IteratedPhytoplankton"]
    Cnew=state.scalar_fields["IteratedChlorophyll"]
    Znew=state.scalar_fields["IteratedZooplankton"]
    Nnew=state.scalar_fields["IteratedNutrient"]
    Anew=state.scalar_fields["IteratedAmmonium"]
    Dnew=state.scalar_fields["IteratedDetritus"]
    coords=state.vector_fields["Coordinate"]


    P_source=state.scalar_fields["PhytoplanktonSource"]
    C_source=state.scalar_fields["ChlorophyllSource"]
    Z_source=state.scalar_fields["ZooplanktonSource"]
    N_source=state.scalar_fields["NutrientSource"]
    N_abs=state.scalar_fields["NutrientAbsorption"]
    A_source=state.scalar_fields["AmmoniumSource"]
    D_source=state.scalar_fields["DetritusSource"]
    try:
        PP=state.scalar_fields["PrimaryProduction"]
    except KeyError:
        PP=None
    try:
        PG=state.scalar_fields["PhytoplanktonGrazing"]
    except KeyError:
        PG=None

    alpha_c=parameters["alpha_c"]
    beta_P=parameters["beta_p"]
    beta_D=parameters["beta_d"]
    delta=parameters["delta"]
    gamma=parameters["gamma"]
    zeta=parameters["zeta"]
    epsilon=parameters["epsilon"]
    psi=parameters["psi"]
    g=parameters["g"]
    k_N=parameters["k_N"]
    k_A=parameters["k_A"]
    k_p=parameters["k_p"]
    k_z=parameters["k_z"]
    v=parameters["v"]
    mu_P=parameters["mu_P"]
    mu_Z=parameters["mu_Z"]
    mu_D=parameters["mu_D"]
    p_P=parameters["p_P"]
    theta_m=parameters["theta_m"]
    lambda_bio=parameters["lambda_bio"]
    lambda_A=parameters["lambda_A"]
    photicZoneLimit=parameters["photic_zone_limit"]
    p_D=1-p_P

    for n in range(P.node_count):
        # Values of fields on this node.
        P_n=max(.5*(P.node_val(n)+Pnew.node_val(n)), 0.0)
        Z_n=max(.5*(Z.node_val(n)+Znew.node_val(n)), 0.0)
        N_n=max(.5*(N.node_val(n)+Nnew.node_val(n)), 0.0)
        A_n=max(.5*(A.node_val(n)+Anew.node_val(n)), 0.0)
        C_n=max(.5*(C.node_val(n)+Cnew.node_val(n)), 0.0)
        D_n=max(.5*(D.node_val(n)+Dnew.node_val(n)), 0.0)
        I_n=max(I.node_val(n), 0.0)
        depth=abs(coords.node_val(n)[2])
 
        # In the continuous model we start calculating Chl-a related 
        # properties at light levels close to zero with a potential /0. 
        # It seems that assuming theta = zeta at very low P and Chl takes
        # care of this most effectively       
        if (P_n < 1e-7 or  C_n < 1e-7):
            theta = zeta
        else:
           theta = C_n/P_n*zeta # C=P_n*zeta
        alpha = alpha_c * theta

        # Light limited phytoplankton growth rate.
        J=(v*alpha*I_n)/(v**2+alpha**2*I_n**2)**0.5	    

        # Nitrate limiting factor.
        Q_N=(N_n*math.exp(-psi * A_n))/(k_N+N_n)

        # Ammonium limiting factor
        Q_A=A_n/(k_A+A_n)

        # Chl growth scaling factor
        # R_P=(theta_m/theta)*J*(Q_N+Q_A)/(alpha*I_n+1e-7) 
        R_P=(theta_m/theta)*(Q_N+Q_A)*v/(v**2+alpha**2*I_n**2)**0.5 

        # Primary production
        X_P=J*(Q_N+Q_A)*P_n

        # Zooplankton grazing of phytoplankton.
	    # It looks a bit different from the original version, however
	    # it is the same function with differently normalised parameters to 
	    # simplify tuning 
        # G_P=(g * epsilon * p_P * P_n**2 * Z_n)/(g+epsilon*(p_P*P_n**2 + p_D*D_n**2))
        G_P=(g * p_P * P_n**2 * Z_n)/(epsilon + (p_P*P_n**2 + p_D*D_n**2))

        # Zooplankton grazing of detritus. (p_D - 1-p_P)
        # G_D=(g * epsilon * (1-p_P) * D_n**2 * Z_n)/(g+epsilon*(p_P*P_n**2 + p_D*D_n**2))
        G_D=(g  * (1-p_P) * D_n**2 * Z_n)/(epsilon + (p_P*P_n**2 + p_D*D_n**2))

        # Death rate of phytoplankton.
	    # There is an additional linear term because we have a unified model
	    # (no below/above photoc zone distinction)
        De_P=mu_P*P_n*P_n/(P_n+k_p)+lambda_bio*P_n

        # Death rate of zooplankton.
	    # There is an additional linear term because we have a unified model
	    # (no below/above photoc zone distinction)
        De_Z=mu_Z*Z_n**3/(Z_n+k_z)+lambda_bio*Z_n

        # Detritus remineralisation.
        De_D=mu_D*D_n+lambda_bio*P_n+lambda_bio*Z_n

        # Ammonium nitrification (only below the photic zone)
	    # This is the only above/below term
        De_A=lambda_A*A_n*(1-photic_zone(depth,100,20))

        P_source.set(n, J*(Q_N+Q_A)*P_n - G_P - De_P)
        C_source.set(n, (R_P*J*(Q_N+Q_A)*P_n + (-G_P-De_P))*theta/zeta)
        Z_source.set(n, delta*(beta_P*G_P+beta_D*G_D) - De_Z)
        D_source.set(n, -De_D + De_P + gamma*De_Z +(1-beta_P)*G_P - beta_D*G_D)
        N_source.set(n, -J*P_n*Q_N+De_A)
        A_source.set(n, -J*P_n*Q_A + De_D + (1 - delta)*(beta_P*G_P + beta_D*G_D) + (1-gamma)*De_Z-De_A)

        if PP:
            PP.set(n, X_P)
        if PG:
            PG.set(n, G_P)

def check_six_component_parameters(parameters):
    from sys import stderr

    valid=True

    if not parameters.has_key("alpha_c"):
        stderr.write("PCZNDA parameter alpha_c missing.\n")
        stderr.write("alpha is the chlorophyll-specific inital slope of P-I curve.\n\n")
        valid = False

    if not parameters.has_key("beta_p"):
        stderr.write("PCZNDA parameter beta_p missing.\n")
        stderr.write("beta is the assimilation efficiency of zooplankton for plankton.\n\n")
        valid = False

    if not parameters.has_key("beta_d"):
        stderr.write("PCZNDA parameter beta_d missing.\n")
        stderr.write("beta is the assimilation efficiency of zooplankton for detritus.\n\n")
        valid = False

    if not parameters.has_key("delta"):
        stderr.write("PCZNDA parameter delta missing.\n")
        stderr.write("delta is the zooplankton excretion parameter.\n\n")
        valid = False

    if not parameters.has_key("gamma"):
        stderr.write("PCZNDA parameter gamma missing.\n")
        stderr.write("gamma is the zooplankton excretion parameter.\n\n")
        valid = False

    if not parameters.has_key("epsilon"):
        stderr.write("PCZNDA parameter epsilon missing.\n")
        stderr.write("epsilon is the grazing parameter relating the rate of prey item to prey density.\n\n")
        valid = False

    if not parameters.has_key("g"):
        stderr.write("PCZNDA parameter g missing.\n")
        stderr.write("g is the zooplankton maximum growth rate.\n\n")
        valid = False

    if not parameters.has_key("k_A"):
        stderr.write("PCZNDA parameter k_A missing.\n")
        stderr.write("k_A is the half-saturation constant for ammonium.\n\n")
        valid = False

    if not parameters.has_key("k_p"):
        stderr.write("PCZNDA parameter k_p missing.\n")
        stderr.write("k_ is something to do with mortatility rate of phytoplankton")

    if not parameters.has_key("k_z"):
        stderr.write("PCZNDA parameter k_z missing.\n")
        stderr.write("k_z is something to do with te mortality rate of zooplankton\n\n")
        valid = False

    if not parameters.has_key("k_N"):
        stderr.write("PCZNDA parameter k_N missing.\n")
        stderr.write("k_N is the half-saturation constant for nutrient.\n\n")
        valid = False

    if not parameters.has_key("mu_P"):
        stderr.write("PCZNDA parameter mu_P missing.\n")
        stderr.write("mu_P is the phytoplankton mortality rate.\n\n")
        valid = False

    if not parameters.has_key("mu_Z"):
        stderr.write("PCZNDA parameter mu_Z missing.\n")
        stderr.write("mu_Z is the zooplankton mortality rate.\n\n")
        valid = False

    if not parameters.has_key("mu_D"):
        stderr.write("PCZNDA parameter mu_D missing.\n")
        stderr.write("mu_D is the detritus remineralisation rate.\n\n")
        valid = False

    if not parameters.has_key("psi"):
        stderr.write("PCZNDA parameter psi missing.\n")
        stderr.write("psi is the strength of ammonium inibition of nitrate uptake\n\n")
        valid = False

    if not parameters.has_key("p_P"):
        stderr.write("PCZNDA parameter p_P missing.\n")
        stderr.write("p_P is the relative grazing preference of zooplankton for phytoplankton.\n\n")
        valid = False

    if not parameters.has_key("v"):
        stderr.write("PCZNDA parameter v missing.\n")
        stderr.write("v is the maximum phytoplankton growth rate.\n\n")
        valid = False

    if not parameters.has_key("theta_m"):
        stderr.write("PCZNDA parameter theta_m missing.\n")
        stderr.write("theta_m is the maximum Chlorophyll to C ratio.\n\n")
        valid = False

    if not parameters.has_key("zeta"):
        stderr.write("PCZNDA parameter zeta missing.\n")
        stderr.write("zeta is the conversion factor from gC to mmolN on C:N ratio of 6.5\n\n")
        valid = False

    if not parameters.has_key("lambda_bio"):
        stderr.write("PCZNDA parameter lambda_bio missing.\n")
        stderr.write("lambda_bio is rate which plankton turn to detritus below photic zone\n\n")
        valid = False

    if not parameters.has_key("lambda_A"):
        stderr.write("PCZNDA parameter lambda_A missing.\n")
        stderr.write("lambda_A nitrification rate below photic zone\n\n")
        valid = False

    if not parameters.has_key("photic_zone_limit"):
        stderr.write("PCZNDA parameter photic_zone_limit missing.\n")
        stderr.write("photic_zone_limit defines the base of the photic zone in W/m2\n\n")
        valid = False

    return valid

def photic_zone(z,limit,transition_length):

    depth = abs(z)
    if (depth < limit):
        return 1.
    elif (depth < limit+transition_length):
        return 1.-(depth-limit)/float(transition_length)
    else:
        return 0.0
