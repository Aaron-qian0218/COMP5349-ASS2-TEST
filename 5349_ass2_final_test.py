# -*- coding: utf-8 -*-
"""5349-ass2-final_code.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1YNDlqrDmqDmmbwg0sYWJYsPf_O0IqDOs
"""

#Initializing spark
from pyspark.sql import SparkSession
#Configure spark settings in sparkSession, such as name, memory size, number of cores, etc.
spark = SparkSession \
    .builder \
    .appName("COMP5349 Assignment2 Dataset")\
    .config("spark.executor.memory", "4g")\
    .config("spark.driver.memory", "6g") \
    .config("spark.executor.cores", "2") \
    .config("spark.sql.inMemoryColumnarStorage.compressed", "true")\
    .config("spark.sql.execution.arrow.enabled", "true")\
    .getOrCreate()

#Load the data and use spark SQL's read.json API to read the data in the JSON file
test_dataset = 'test.json'
testing_df = spark.read.json(test_dataset)

#Display specific data
testing_df.show(1)

#Print the structure diagram of the data
testing_df.printSchema()

"""### **Spark sql解析嵌套JSON文件**"""

#Use select to select rows and explode to expand the array to multiple rows
from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql import Window, Row
from pyspark.sql.types import IntegerType, StringType, FloatType

testing_data_df= testing_df.select((explode("data").alias('data'))) #Select the data column in testing_df
testing_paragraph_df = testing_data_df.select(explode("data.paragraphs").alias("paragraph")) #Expand the data column to get the paragraph column in the data column

testing_paragraph_df.show(5)

paragraphs_context_qas_df = testing_paragraph_df.select(
    col("paragraph.context").alias("paragraph_context"),  #Select the context data in the paragraph column in testing_paragraph_df
    (explode("paragraph.qas").alias('qas'))) #extended qas column

qas_answers_df = paragraphs_context_qas_df.select(
    col("paragraph_context"), #Select the paragraph_context column in paragraphs_context_qas_df
    col("qas.question").alias("qas_question"), #Select the question data in the qas column in paragraphs_context_qas_df
    col("qas.is_impossible").alias("qas_is_impossible"), #Select is_impossible data in qas column in paragraphs_context_qas_df
    explode_outer("qas.answers").alias('answers'), #Select answers data in column qas in paragraphs_context_qas_df
)

final_table_df = qas_answers_df.select(
    col("paragraph_context"), #Select the paragraph_context column in qas_answers_df
    col("qas_question"), #Select the qas_question column in qas_answers_df
    col("qas_is_impossible"), #Select the qas_is_impossible column in qas_answers_df
    col("answers.answer_start").alias("answer_start"), #Select the answer_start data in the answers column in qas_answers_df and rename it to answer_start
    col("answers.text").alias("answer_text"), #Select the text data in the answers column in qas_answers_df and rename it to answer_text
)

final_table_df.show(5)

"""### **Create positive samples**"""

#Find contracts with answers to questions and display them
possible_sample_df = final_table_df.where(
    col("qas_is_impossible") == False
) #Select the data whose value is False in the qas_is_impossible column in the final_table_df list, and display
possible_sample_df.show(5)

#Convert the previous data from the dataframe form to the RDD form, which is convenient for subsequent calculation and filtering operations
possible_sample_rdd = possible_sample_df.rdd
possible_sample_rdd.take(3)

#Use map to convert data from row type to tuple type, which is convenient for subsequent operations
def row_to_tuple(row):
  return tuple(row)
possible_sample_rdd_tuple = possible_sample_rdd.map(row_to_tuple).cache()
possible_sample_rdd_tuple.take(3)

#Cut the contract according to a certain window size and step size, and find the positive samples and Possible negative samples in these sequences
import random
def create_possible_sample(record):
  '''
  根据4096的窗口大小和2048的步长对文本进行切割得到文本序列。
  根据答案在文本中出现的位置，来判断序列是否含有答案或者部分含有答案，如果是则判断为positive samples，否则为Possible negative samples
  '''
  output_list = [] #Create output_list list to save output
  poss_record = [] #Create a poss_record list to save positive samples
  neg_record = [] #Create neg_record list to hold Possible negative samples
  subStrings = [] #Create a list of subStrings to hold the cut text sequence
  window = 4096
  stride = 2048
  answer_start = record[3]
  answer_end = record[3] + len(record[4]) #Use the length of the answer text to calculate the end position of the answer in the text
  length_record = len(record[0])
  for i in range(0, length_record, stride):
    if i+window <= length_record: #When the end position of the current window is smaller than the text position
      temp = record[0][i:i+window] #Output the data from i to i + window in the list
    else: #When the end position of the current window is larger than the text position
      temp = record[0][i:] #Output the data from i to any number of ends in the list
    subStrings.append(temp) #Use the subStrings list to save the cut text sequence
  for j in range(len(subStrings)):
    if (j * stride <= answer_start) and (answer_start < j * stride + window) and (j * stride + window < answer_end): #When the starting position of the answer is in the sequence, the sequence must be positive samples because it must contain part of the answer
      poss_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=answer_start - j * stride, answer_end=window))
    elif(j * stride <= answer_start) and (answer_start < j * stride + window) and (answer_end < j * stride + window): #When the start position of the sequence is larger than the start position of the answer and the end position is smaller than the end position of the answer, this sequence must be positive samples
      poss_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=answer_start - j * stride, answer_end=answer_end-j * stride))
    elif(answer_start <= j * stride) and (j * stride + window < answer_end): #When the sequence contains all the answer content, this sequence must be positive samples
      poss_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=0, answer_end=window))
    elif(j * stride <= answer_end) and (answer_end < j * stride + window) and (answer_start < j * stride): #Same as the first judgment, when the end position of the answer is in the sequence, the sequence must be positive samples
      poss_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=0, answer_end=answer_end-j * stride))
    else: 
      neg_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=0, answer_end=0))
  if (len(poss_record)<len(neg_record)):
    random.shuffle(neg_record) #Re-randomly sort the list of negative samples to maintain the uniqueness of the sequence of Possible negative samples
    neg_record = neg_record[:len(poss_record)] #Take the same number of possible negative samples as positive samples
  poss_record.extend(neg_record)
  return poss_record

poss_rdd = possible_sample_rdd_tuple.flatMap(create_possible_sample).cache()
poss_rdd.take(3)

"""### **Create negative sample**"""

#Count the number of contracts that contain poss_record for each question
possible_contract = possible_sample_df.groupBy("qas_question").count().withColumnRenamed("count","positive_contract_num")
possible_contract.show(5)

#Convert the positive samples and Possible negative samples just obtained from rdd to dataframe form
poss_dfColumns = ["data_source","qas_question","answer_start","answer_end"]
poss_df = poss_rdd.toDF(poss_dfColumns).cache()
poss_df.show(3)

#Count the number of positive samples for each question. (If the start and end of the answer are not 0, it means positive samples)
positive_simple_df = poss_df.where(col("answer_start") != '0')
positive_simple_num_df = positive_simple_df.where(col("answer_end") != '0').groupBy("qas_question").count().withColumnRenamed("count","positive_simple_num")
positive_simple_num_df.show(5)

#The number of contracts containing poss_record and the number of positive samples for each question just calculated for each question are stored in a dataframe
count_table = final_table_df.where(
  col("qas_is_impossible") == True
).join(positive_simple_num_df,"qas_question")
count_table = count_table.join(possible_contract,"qas_question").cache()
count_table.show(5)

#Convert dataframes containing various numbers to rdd form for subsequent calculations
count_table_rdd = count_table.rdd
count_table_rdd = count_table_rdd.map(row_to_tuple)
count_table_rdd.take(5)

#Calculate the number of Impossible negative samples
def count_negtive_sample(record):
  '''
  按照公式：每个问题positive samples的数量/每个问题含有poss_record的contract的数量 计算Impossible negative samples应该取的数量
  '''
  output = []
  #Determine whether the fractional part of the result is greater than 0.5, if it is greater than 0.5, enter 1, if it is small, discard it
  if record[5] % record[6] == 0:
    n = record[5] / record[6]
  elif (record[5] % record[6] != 0) and (float(record[5] / record[6])-int(record[5] / record[6]) >= 0.5):
    n = record[5]//record[6]+1
  elif (record[5] % record[6] != 0) and (record[5] / record[6] - record[5] // record[6] <= 0.5):
    n = record[5]//record[6]
  output.append((record[0],record[1],record[2],record[3],record[4],n))
  return output
count_netiv_num_rdd = count_table_rdd.flatMap(count_negtive_sample)
count_netiv_num_rdd.take(5)

#Cut the contract according to a certain window size and step size to obtain Impossible negative samples
def create_negative_sample(record):
  neg_record = []
  subStrings = []
  window = 4096
  stride = 2048
  num = int(record[5])
  length_record = len(record[0])
  #Split contracts by step size and window size
  for i in range(0, length_record, stride):
    if i+window <= length_record:
      temp = record[0][i:i+window]
    else:
      temp = record[0][i:]
    subStrings.append(temp)
  for j in range(len(subStrings)):
      neg_record.append(Row(source=record[0][j*stride:j*stride+window], question=record[1], answer_start=0, answer_end=0))
  random.shuffle(neg_record) #Re-shuffle the sequence
  neg_record = neg_record[:num] #Take a specific number of Impossible negative samples
  return neg_record
imposs_rdd = count_netiv_num_rdd.flatMap(create_negative_sample).cache()
imposs_rdd.take(3)

"""### **Output**"""

#Merge the obtained positive samples and negative samples to get the final output rdd
output_rdd = poss_rdd.union(imposs_rdd)
output_rdd.take(5)

#Convert the output rdd into a dataframe in the required format
output_rddColumns = ["source","question","answer_start","answer_end"]
output_df = output_rdd.toDF(output_rddColumns).cache()
output_df.show()

# Calculate the number of outputs
output_df.count()

#Save the output in a JSON file
output_df.write.json("output.json")