def identify_arm(
    support,
    t,
    s,
    assumptions=True
):
    """
    Identification rule.

    Return POINT functional if
    pi_i(t,s)>0 and assumptions hold.
    """


    # check assumptions

    if assumptions is False:

        return {
            "status":"NOT IDENTIFIED",
            "reason":
            "Required assumptions are not satisfied"
        }



    arm=(t,s)



    # check support

    if support.get(arm,0)==0:

        return {
            "status":"NOT IDENTIFIED",
            "reason":
            "Zero support for this arm"
        }



    # POINT functional

    return {
        "status":"POINT",
        "arm":arm,
        "functional":
        f"mu_i({t},{s})=E[Y_i_obs | A,X,T_i={t},S_i={s}]"
    }