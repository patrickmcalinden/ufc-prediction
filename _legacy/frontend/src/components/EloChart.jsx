import React from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";

export default function EloChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="text-gray-500 font-medium italic p-4 text-center">No structural Elo history logged computationally.</div>;
  }

  return (
    <div className="w-full h-[400px]">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
          <XAxis 
            dataKey="rating_date" 
            stroke="#888888" 
            fontSize={12} 
            tickFormatter={(val) => new Date(val).getFullYear()} 
          />
          <YAxis domain={['auto', 'auto']} stroke="#888888" fontSize={12} width={40} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '12px', padding: '12px' }}
            itemStyle={{ fontWeight: 'bold' }}
            labelFormatter={(val) => new Date(val).toLocaleDateString()}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }}/>
          <Line 
            type="monotone" 
            dataKey="elo_standard" 
            stroke="#ffffff" 
            strokeWidth={2}
            dot={false} 
            name="Standard Elo" 
          />
          <Line 
            type="monotone" 
            dataKey="elo_modified" 
            stroke="#D20A11" 
            strokeWidth={4}
            dot={false} 
            name="Modified Elo (Active Vector)" 
            activeDot={{ r: 8, fill: '#D20A11', stroke: '#fff', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
