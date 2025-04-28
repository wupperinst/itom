#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jul  6 23:49:44 2019

@author: dariyoushsh

"""

def color(text, **user_styles):
    '''
    Takes text and the ANSI color code and returnes the selected styled text.
    '''
    styles = {
        # styles
        'bold': '\033[01m',
        'underline': '\033[04m',
        'italic': '\033[03m',
        # text colors 
        'fg_black': '\033[30m',
        'fg_red': '\033[31m',
        'fg_green': '\033[32m',
        'fg_orange': '\033[33m',
        'fg_blue': '\033[34m',
        'fg_purple': '\033[35m',
        'fg_cyan': '\033[36m',
        'fg_light_grey': '\033[37m',
        # background colors
        'bg_black': '\033[40m',
        'bg_red': '\033[41m',
        'bg_green': '\033[42m',
        'bg_orange': '\033[43m',
        'bg_blue': '\033[44m',
        'bg_purple': '\033[45m',
        'bg_cyan': '\033[46m',
        'bg_light_grey': '\033[47m'
    }

    color_text = ''
    for style in user_styles:
        try:
            color_text += styles[style]
        except KeyError:
            raise KeyError('def color: parameter `{}` does not exist'.format(style))
            
    color_text += text
    return '\033[0m{}\033[0m'.format(color_text)


# Functions that take a text and return a specified color and style
def red(text):
    return color(text, bold = True, fg_red = True)

def orange(text):
    return color(text, bold = True, fg_orange = True)

def green(text):
    return color(text, bold = True, fg_green = True)

def cyan(text):
    return color(text, bold = True, fg_cyan = True)
