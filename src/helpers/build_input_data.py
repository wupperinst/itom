#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper methods to prepare input data

@author: mathieusa
"""
import os
import pandas as pd
import numpy as np

############################################################################
# Build PARAMETERS from input data

def _build_transport_params(config, input_path):
    '''
    TransportRoute
    TransportCapacity
    TransportCostByMode
    '''
    # NOTE: TEMPORARY CODE!!!
    df_prod = pd.read_csv(os.path.join(input_path, 'PRODUCT.csv'))
    df_loc = pd.read_csv(os.path.join(input_path, 'LOCATION.csv'))
    df_reg = pd.read_csv(os.path.join(input_path, 'REGION.csv'))
    df_geo = pd.read_csv(os.path.join(input_path, 'Geography.csv'))
    # Keep only LOCATIONS that are not TRANSPORT_HUB
    df_loc=df_loc[~df_loc['LOCATION'].str.contains('TRANSPORT_HUB')]
    df_geo=df_geo[~df_geo['LOCATION'].str.contains('TRANSPORT_HUB')]

    # Build TransportRoute and TransportCapacity parameters

    # WITH Transport Hub
    if config['transport']['hub']:
            data = []
            # Within each region, each location is linked via OTHER to the hub for each product
            for r in df_reg['REGION']:
                RELEVANT_LOCATION = [loc for loc in df_geo.loc[(df_geo.REGION==r) & (df_geo.Geography==1),'LOCATION']]
                for loc in RELEVANT_LOCATION:
                    for p in df_prod['PRODUCT']:
                        for y in config['years']:
                            data.append({
                                    'LOCATION1': loc,
                                    'LOCATION2': loc,
                                    'PRODUCT': p,
                                    'TRANSPORTMODE': 'ONSITE',
                                    'YEAR':y,
                                    'TransportRoute': 1,
                                    'TransportCapacity': 1e20
                                    })
                            data.append({
                                    'LOCATION1': loc,
                                    'LOCATION2': 'TRANSPORT_HUB_'+r,
                                    'PRODUCT': p,
                                    'TRANSPORTMODE': 'OTHER',
                                    'YEAR':y,
                                    'TransportRoute': 1,
                                    'TransportCapacity': 1e20
                                    })
                            data.append({
                                    'LOCATION1': 'TRANSPORT_HUB_'+r,
                                    'LOCATION2': loc,
                                    'PRODUCT': p,
                                    'TRANSPORTMODE': 'OTHER',
                                    'YEAR':y,
                                    'TransportRoute': 1,
                                    'TransportCapacity': 1e20
                                    })
            # Each region is linked via INTER_REG to every other region via the Hubs for each product
            for r1 in df_reg['REGION']:
                for r2 in df_reg['REGION']:
                    for p in df_prod['PRODUCT']:
                        if r1 != r2:
                            for y in config['years']:
                                data.append({
                                        'LOCATION1': 'TRANSPORT_HUB_'+r1,
                                        'LOCATION2': 'TRANSPORT_HUB_'+r2,
                                        'PRODUCT': p,
                                        'TRANSPORTMODE': 'INTER_REG',
                                        'YEAR':y,
                                        'TransportRoute': 1,
                                        'TransportCapacity': 1e20
                                        })
    else:
    # WITHOUT Transport Hub
    # Each location is linked via OTHER to every other location for each product
        data = []
        for loc1 in df_loc['LOCATION']:
            for loc2 in df_loc['LOCATION']:
                for p in df_prod['PRODUCT']:
                    if loc1 == loc2:
                        for y in config['years']:
                            data.append({
                                    'LOCATION1': loc1,
                                    'LOCATION2': loc2,
                                    'PRODUCT': p,
                                    'TRANSPORTMODE': 'ONSITE',
                                    'YEAR':y,
                                    'TransportRoute': 1,
                                    'TransportCapacity': 1e20
                                    })
                    else:
                        for y in config['years']:
                            data.append({
                                    'LOCATION1': loc1,
                                    'LOCATION2': loc2,
                                    'PRODUCT': p,
                                    'TRANSPORTMODE': 'OTHER',
                                    'YEAR':y,
                                    'TransportRoute': 1,
                                    'TransportCapacity': 1e20
                                    })

    df_tr = pd.DataFrame(data)
    df_tr_route = df_tr[['LOCATION1', 'LOCATION2', 'PRODUCT', 'TRANSPORTMODE', 'YEAR', 'TransportRoute']]
    df_tr_cap = df_tr[['LOCATION1', 'LOCATION2', 'PRODUCT', 'TRANSPORTMODE', 'YEAR', 'TransportCapacity']]

    df_tr_route_pipe = pd.read_csv(os.path.join(input_path, 'TransportRoute_pipeline.csv'))
    df_tr_route_pipe.rename({'LOCATION':'LOCATION1','LOCATION.1':'LOCATION2'}, axis='columns', inplace=True)
    df_tr_route = pd.concat([df_tr_route, df_tr_route_pipe], sort=False)

    df_tr_cap_pipe = pd.read_csv(os.path.join(input_path, 'TransportCapacity_pipeline.csv'))
    df_tr_cap_pipe.rename({'LOCATION':'LOCATION1','LOCATION.1':'LOCATION2'}, axis='columns', inplace=True)
    df_tr_cap = pd.concat([df_tr_cap, df_tr_cap_pipe], sort=False)

    df_tr_route.rename({'LOCATION1':'LOCATION', 'LOCATION2':'LOCATION'}, axis='columns', inplace=True)
    df_tr_cap.rename({'LOCATION1':'LOCATION', 'LOCATION2':'LOCATION'}, axis='columns', inplace=True)

    return df_tr_route, df_tr_cap
