

import React, {Component} from 'react'
import Form from 'antd/es/form';
import Card from 'antd/es/card'
import Checkbox from 'antd/es/checkbox'
import Row from 'antd/es/row'
import Col from 'antd/es/col'
import DatePicker from 'antd/es/date-picker'
import Button from 'antd/es/button'

import { FormComponentProps } from 'antd/lib/form';
import { allSavedCondition } from '../components/saved-search';
import moment from 'moment'
import { GetFieldDecoratorOptions } from 'antd/lib/form/Form';
import { dateFormat, disabledFuture } from '@/utils/common';

import {keyTextMap} from '../components/fund-line'
const { RangePicker } = DatePicker;
let [curYear, curMonth, curDate] = dateFormat(new Date()).split('-').map(Number)
curMonth = Number(curMonth) - 1


const excludeList: (keyof typeof keyTextMap)[] = ['fundVal', 'dateBuyAmount', 'dateSellAmount', 'buy','fixedBuy','sell']

const checkList: (keyof typeof keyTextMap)[] = ['totalAmount','leftAmount', 'profitRate', 'profit', 'fundAmount', 'fundGrowthRate', 'maxPrincipal','accumulatedProfit', 'totalProfitRate', 'position']

interface CompareFormProp extends FormComponentProps{
  onSearch: (val: CompareFormObj)=>void
}
export interface CompareFormObj {

  stragegyChecked: string[]


  chartChecked: string[]
  dateRange: [any, any]
}

const formItemLayout = {
  // style: {
  //   width: 500
  // },
  labelCol: {
    xs: { span: 24 },
    sm: { span: 4 },
  },
  wrapperCol: {
    xs: { span: 24 },
    sm: { span: 20 },
  },
};


export class CompareForm extends  Component<CompareFormProp> {


  handleSubmit = e => {
    e.preventDefault();
    this.props.form.validateFields((err, values) => {
      if (!err) {
        console.log('compare', values)
        this.props.onSearch(values)
      }
    });
  }

  render() {
    const { getFieldDecorator } = this.props.form


    const rangeConfig: GetFieldDecoratorOptions = {
      rules: [{ type: 'array', required: true, message: 'time' }],
      initialValue: [moment([Number(curYear) - 1, curMonth, curDate]), moment([curYear, curMonth, curDate])]
    };
    return <Card title="142"  style={{
      textAlign: 'initial',
      margin: '20px 0'
    }} >
      <Form  onSubmit={this.handleSubmit} >
      <Form.Item {...formItemLayout} label="147" >
        {
          getFieldDecorator<CompareFormObj>('stragegyChecked', {
            rules: [{ required: true, message: '156' }],
          })(<Checkbox.Group style={{ width: '100%' }}>
            {Object.keys(allSavedCondition).map((tagName,index) => <Checkbox key={index} value={tagName}>{tagName}</Checkbox>)}
        </Checkbox.Group>)
        }
        </Form.Item>

        <Form.Item {...formItemLayout} label="data" >
        {
          getFieldDecorator<CompareFormObj>('chartChecked', {
            initialValue: ['totalAmount', 'accumulatedProfit', 'totalProfitRate', 'position'],
            rules: [{ required: true, message: 'choose one data' }],
          })(<Checkbox.Group style={{ width: '100%' }}>
            {checkList.map((key,index) => <Checkbox key={index} value={key}>{keyTextMap[key]}</Checkbox>)}
        </Checkbox.Group>)
        }
        </Form.Item>


        <Form.Item {...formItemLayout} label="time">
          {getFieldDecorator<CompareFormObj>('dateRange', rangeConfig)(
            <RangePicker
              placeholder={['begin', 'end']}
              ranges={{
                'recent one year': [moment([Number(curYear) - 1, curMonth, curDate]), moment([curYear, curMonth, curDate])],
                'recent two year': [moment([Number(curYear) - 2, curMonth, curDate]), moment([curYear, curMonth, curDate])],
                'recent three year': [moment([Number(curYear) - 3, curMonth, curDate]), moment([curYear, curMonth, curDate])],
                'recent four year': [moment([Number(curYear) - 5, curMonth, curDate]), moment([curYear, curMonth, curDate])],
              }}
              disabledDate={disabledFuture} />)}
        </Form.Item>

        <Form.Item wrapperCol={{   offset: 4 }}>
          <Button type="primary" htmlType="submit">

          </Button>
        </Form.Item>

        </Form>
      </Card>
  }
}

export const CompareSearchForm = Form.create<CompareFormProp>({ name: 'compare-search' })(CompareForm);
