def print_and_log(text):
    print(text)
    log_file.write(text + '\n')


log_file = open('logs.txt', 'w')

print_and_log('gostei daqui', log_file)
print_and_log('gostei mesmo', log_file)

log_file.close()