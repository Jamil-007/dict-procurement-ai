'use client';

import React from 'react';
import { Skeleton } from '@/components/ui/skeleton';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export function ReportSkeleton() {
  return (
    <div className="h-full w-full overflow-y-auto p-6 space-y-6 bg-white">
      {/* Header Skeleton */}
      <div className="space-y-4">
        <Skeleton className="h-8 w-3/4 shimmer bg-gray-200" />
        <Skeleton className="h-4 w-1/2 shimmer bg-gray-200" />
      </div>

      {/* Document Info Card */}
      <Card className="border-2 border-gray-200 rounded-2xl">
        <CardHeader>
          <Skeleton className="h-6 w-1/3 shimmer bg-gray-200" />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24 shimmer bg-gray-200" />
            <Skeleton className="h-4 w-32 shimmer bg-gray-200" />
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24 shimmer bg-gray-200" />
            <Skeleton className="h-4 w-40 shimmer bg-gray-200" />
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24 shimmer bg-gray-200" />
            <Skeleton className="h-4 w-28 shimmer bg-gray-200" />
          </div>
        </CardContent>
      </Card>

      {/* Executive Summary Card */}
      <Card className="border-2 border-gray-200 rounded-2xl">
        <CardHeader>
          <Skeleton className="h-6 w-1/4 shimmer bg-gray-200" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-full shimmer bg-gray-200" />
          <Skeleton className="h-4 w-full shimmer bg-gray-200" />
          <Skeleton className="h-4 w-5/6 shimmer bg-gray-200" />
          <Skeleton className="h-4 w-full shimmer bg-gray-200" />
          <Skeleton className="h-4 w-4/5 shimmer bg-gray-200" />
        </CardContent>
      </Card>

      {/* Findings Card */}
      <Card className="border-2 border-gray-200 rounded-2xl">
        <CardHeader>
          <Skeleton className="h-6 w-1/3 shimmer bg-gray-200" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((item) => (
            <div key={item} className="space-y-2">
              <Skeleton className="h-5 w-1/4 shimmer bg-gray-200" />
              <div className="pl-4 space-y-2">
                <Skeleton className="h-3 w-full shimmer bg-gray-200" />
                <Skeleton className="h-3 w-5/6 shimmer bg-gray-200" />
                <Skeleton className="h-3 w-4/5 shimmer bg-gray-200" />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Recommendations Card */}
      <Card className="border-2 border-gray-200 rounded-2xl">
        <CardHeader>
          <Skeleton className="h-6 w-1/3 shimmer bg-gray-200" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-4 w-full shimmer bg-gray-200" />
          <Skeleton className="h-4 w-full shimmer bg-gray-200" />
          <Skeleton className="h-4 w-5/6 shimmer bg-gray-200" />
        </CardContent>
      </Card>

      {/* Chart Skeleton */}
      <Card className="border-2 border-gray-200 rounded-2xl">
        <CardHeader>
          <Skeleton className="h-6 w-1/4 shimmer bg-gray-200" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full shimmer bg-gray-200" />
        </CardContent>
      </Card>
    </div>
  );
}
