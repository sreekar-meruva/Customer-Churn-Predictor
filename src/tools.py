from typing import DefaultDict, Dict

def getScalingFeatureDict(features: Dict) -> Dict[list]:
    scalingOptions = DefaultDict(list)
    for key, value in features:
        scalingOptions[value].append(key)
    return(scalingOptions)