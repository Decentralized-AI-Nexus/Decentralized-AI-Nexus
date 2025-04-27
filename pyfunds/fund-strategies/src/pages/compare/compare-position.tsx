

import React, {Component} from 'react'
import { Chart, Axis, Geom, Legend, Tooltip } from 'bizcharts'
import { CommonFundLineProp } from '../components/common-line'
import DataSet from "@antv/data-set";
export interface CompareChartDataItem {
  name: string
  avgPos: number
  maxPos: number
  profitPerInvest: number

  profitAmountPerPos: number
}

interface ComparePositionProp extends Omit<CommonFundLineProp, 'data'|'y'> {
  data: CompareChartDataItem[]
}


export class ComparePosition extends Component<ComparePositionProp> {
  render() {
    const { title,subTitle,  data, textMap, commonProp, legendProp } = this.props
    const commonChartProp = commonProp.chart

    const ds = new DataSet();
    console.log('Position comparison data', data)
    const dv = ds.createView().source(data);
    dv.transform({
      type: "fold",
      fields: ["avgPos", "maxPos"],

      key: "type",

      value: "value"
    });
    const scale = {
      avgPos: {
        alias: `1`
      },
      maxPos: {
        alias: `13`
      }
    }

    return <div>
    <h1 className="main-title" >

      </h1>
    <Chart data={dv}  {...commonChartProp} forceFit scale={scale} >
        <Legend
          itemFormatter={val => {
            return textMap[val]
          }}
         />
        <Axis name="name" />
        <Axis name="value"  />
        <Tooltip />


        <Geom type="interval" color={"type"} position="name*value" adjust={[
              {
                type: "dodge",
                marginRatio: 1 / 32
              }
            ]} />
    </Chart>

    <h1 className="main-title" >

    </h1>
    <Chart data={data}  {...commonChartProp} forceFit scale={scale} >

        <Axis name="name" />
        <Axis name="profitPerInvest"  />
        <Tooltip />

        <Geom type="interval"  position="name*profitPerInvest"   />
    </Chart>

    <h1 className="main-title" >

    </h1>
    <Chart data={data}  {...commonChartProp} forceFit scale={scale} >

        <Axis name="name" />
        <Axis name="profitAmountPerPos"  />
        <Tooltip />

        <Geom type="interval"  position="name*profitAmountPerPos"   />
    </Chart>
    </div>
  }
}
