# -*- coding: utf-8 -*-
#!/usr/bin/env python

import io
import os
import re
import subprocess

from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont




class Video(object):

    def __init__(self, filename):
        self.filename = filename
        self.filesize = self.getFileSize()
        self.duration = self.getVideoDuration()

        example = self.getFrameAt(1)
        self.resolution = example.size
        self.mode = example.mode

        self.thumbnails = []
        self.thumbsize = self.resolution
        self.thumbcount = 0

    def getResolution(self):
        cmd = ["ffmpeg", "-i", self.filename]
        bo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).stdout.read()
        bstr = io.BytesIO(bo).read()
        metainfo = bstr.decode('UTF-8')
        match = re.search(r'\d{3,5}x\d{3,5}', metainfo)
        width, height = match.group(0).split('x')
        return (int(width), int(height))

    def getFileSize(self):
        return os.stat(self.filename).st_size / 1048576.0

    def getVideoDuration(self):
        p = subprocess.Popen(["ffmpeg", "-i", self.filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        pout = p.communicate()
        matches = re.search(r"Duration:\s{1}(?P<hours>\d+?):(?P<minutes>\d+?):(?P<seconds>\d+\.\d+?),", str(pout[0]), re.DOTALL).groupdict()
        hours = Decimal(matches['hours'])
        minutes = Decimal(matches['minutes'])
        seconds = Decimal(matches['seconds'])
        duration = 3600 * hours + 60 * minutes + seconds
        return duration

    def getFrameAt(self, seektime):
        timestring = self.getTimeString(seektime)
        #cmd = "ffmpeg -ss {timestring} -t 1 -i {filename} -f mjpeg -".format(**{'timestring': timestring, 'filename': self.filename})
        cmd = "ffmpeg -ss {timestring} -t 1 -i \"{filename}\" -f mjpeg -".format(**{'timestring': timestring, 'filename': self.filename})

        pout = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True).stdout.read()

        try:
            img = Image.open(io.BytesIO(pout))
        except IOError as err:
            return None
        return img

    def makeThumbnails(self, interval):
        totalThumbs = self.duration // interval
        thumbsList = []
        seektime = 0
        for n in range(0, int(totalThumbs)):
            seektime += interval
            img = self.getFrameAt(seektime)
            if img != None:
                thumbsList.append(img)
        self.thumbnails = thumbsList
        self.thumbcount = len(thumbsList)
        return thumbsList

    def shrinkThumbs(self, maxsize):
        if self.thumbcount == 0:
            return
        for i in range(0, self.thumbcount):
            self.thumbnails[i].thumbnail(maxsize)
        self.thumbsize = self.thumbnails[0].size
        return self.thumbnails

    def getTimeString(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        timestring = "{0:02n}:{1:02n}:{2:02n}".format(hours, minutes, seconds)
        return timestring



class Sheet(object):

    def __init__(self, video):
        fontfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Cabin-Regular-TTF.ttf")
        self.font = ImageFont.truetype(fontfile, 15)
        self.backgroundColour = (0, 0, 0, 0)
        self.textColour = (255, 255, 255, 0)
        self.headerSize = 100
        self.gridColumn = 5
        self.maxThumbSize = (220, 220)
        self.timestamp = True

        self.video = video
        self.sheet = None

    def setProperty(self, prop, value):
        if prop == 'font':
            self.font = ImageFont.truetype(value[0], value[1])
        elif prop == 'backgroundColour':
            self.backgroundColour = value
        elif prop == 'textColour':
            self.textColour = value
        elif prop == 'headerSize':
            self.headerSize = value
        elif prop == 'gridColumn':
            self.gridColumn = value
        elif prop == 'maxThumbSize':
            self.maxThumbSize = value
        elif prop == 'timestamp':
            self.timestamp = value
        else:
            raise Exception('Invalid Sheet property')

    def makeGrid(self):
        column = self.gridColumn
        row = self.video.thumbcount // column
        if (self.video.thumbcount % column) > 0:
            row += 1
        width = self.video.thumbsize[0]
        height = self.video.thumbsize[1]
        grid = Image.new(self.video.mode, (width * column, height * row))
        d = ImageDraw.Draw(grid)
        seektime = 0
        for j in range(0, row):
            for i in range(0, column):
                if j * column + i >= self.video.thumbcount:
                    break
                grid.paste(self.video.thumbnails[j * column + i], (width * i, height * j))
                if self.timestamp == True:
                    seektime += self.vid_interval
                    ts = self.video.getTimeString(seektime)
                    d.text((width * i, height * j), ts, font=self.font, fill=self.textColour)
        self.grid = grid
        return grid

    def makeHeader(self):
        width = self.video.resolution[0]
        height = self.video.resolution[1]
        duration = self.video.duration
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        timestring = "{0:4n}:{1:02n}:{2:02n}".format(hours, minutes, seconds)

        header = Image.new(self.grid.mode, (self.grid.width, self.headerSize), self.backgroundColour)
        d = ImageDraw.Draw(header)
        d.text((10, 10), "File Name: " + os.path.basename(self.video.filename), font=self.font, fill=self.textColour)
        d.text((10, 30), "File Size: " + ("{:10.6f}".format(self.video.filesize)) + " MB", font=self.font, fill=self.textColour)
        d.text((10, 50), "Resolution: " + str(width) + "x" + str(height), font=self.font, fill=self.textColour)
        d.text((10, 70), "Duration: " + timestring, font=self.font, fill=self.textColour)
        self.header = header
        return header

    def makeSheetByInterval(self, interval):
        self.vid_interval = interval
        self.video.makeThumbnails(interval)
        self.video.shrinkThumbs(self.maxThumbSize)
        self.makeGrid()
        self.makeHeader()
        self.sheet = Image.new(self.grid.mode, (self.grid.width, self.grid.height + self.header.height))
        self.sheet.paste(self.header, (0, 0))
        self.sheet.paste(self.grid, (0, self.header.height))
        return self.sheet

    def makeSheetByNumber(self, numOfThumbs):
        interval = (self.video.duration / numOfThumbs)
        self.vid_interval = interval
        return self.makeSheetByInterval(interval)

    def save(self, path):
        if self.sheet:
            with open(path, 'wb') as f:
                self.sheet.save(f)
