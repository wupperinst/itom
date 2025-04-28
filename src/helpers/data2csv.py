#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Helper script to export all sheets of an Excel file to csv
in a specified directory.
"""

import os
import xlrd
import unicodecsv as csv

def xlsx2csv(xlsx_file, csv_path, sheets=[]):
    '''
    Parameters
    ----------
    xlsx_file : string
        Path + xlsx file name from which to export sheets to csv.
    csv_path : string
        Path where to save extracted csv files.
    sheets : list, optional
        List of sheets to export to csv. The default is [].

    Returns
    -------
    None.

    '''

    workbook = xlrd.open_workbook(xlsx_file)
    if not sheets:
        sheets = workbook.sheet_names()

    long_sheet_names = {'LocalAnnualMax...Investment': 'LocalTotalAnnualMaxCapacityInvestment',
                        'LocalAnnualMin...Investment': 'LocalTotalAnnualMinCapacityInvestment',
                        'Total...AnnualActivityLoLimit': 'TotalTechnologyAnnualActivityLowerLimit',
                        'Total...AnnualActivityUpLimit': 'TotalTechnologyAnnualActivityUpperLimit',
                        'Total...AnnualProductionLoLimit': 'TotalTechnologyAnnualProductionLowerLimit'}
    
    for s in sheets:
        
        sheet = workbook.sheet_by_name(s)
        
        if s not in long_sheet_names.keys():
            csv_file_name = s + '.csv'
        else:
            csv_file_name = long_sheet_names[s] + '.csv'
            
        csvfile = open(os.path.join(csv_path,csv_file_name), 'wb')
        csv_wr = csv.writer(csvfile, quoting=csv.QUOTE_NONNUMERIC)
        
        for rownum in range(sheet.nrows):
            row_list = list(x for x in sheet.row_values(rownum))
            for idx, item in enumerate(row_list):
                if isinstance(item, float) and item == int(item):
                    row_list[idx] = int(item)
            csv_wr.writerow(row_list)
        csvfile.close()        

#####
#input_xlsx = os.path.join(os.pardir, os.pardir, 'input', 'dev', 'dev_input.xlsx')
#csv_path = os.path.join(os.pardir, os.pardir, 'input', 'dev')

#xlsx2csv(input_xlsx, csv_path)