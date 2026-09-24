import base64


def convert_names_to_base64(input_file='names.txt', output_file='base64.txt'):
    """
    读取 names.txt 中的中文人名，将其转换为 base64 编码，
    并保存到 base64.txt 中，保持行数对应。
    """
    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
                open(output_file, 'w', encoding='utf-8') as outfile:

            for line_num, line in enumerate(infile, start=1):
                # 去除行末的换行符等空白字符
                original_name = line.rstrip('\n\r ')

                # 将字符串编码为 UTF-8 字节，然后进行 base64 编码
                utf8_bytes = original_name.encode('utf-8')
                base64_bytes = base64.b64encode(utf8_bytes)
                base64_string = base64_bytes.decode('ascii')  # 将 bytes 转回字符串

                # 写入 base64 编码后的字符串，并添加换行符
                outfile.write(base64_string + '\n')

                # 可选：打印进度信息
                print(f"已处理第 {line_num} 行: '{original_name}' -> '{base64_string}'")

        print(f"\n转换完成！结果已保存到 {output_file}")

    except FileNotFoundError:
        print(f"错误：找不到文件 {input_file}")
    except Exception as e:
        print(f"处理文件时发生错误: {e}")


if __name__ == "__main__":
    convert_names_to_base64()