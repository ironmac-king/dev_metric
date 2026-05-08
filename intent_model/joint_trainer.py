"""
Joint Intent + NER Trainer
联合训练意图分类和命名实体识别 - 使用PyTorch原生训练
"""

import json
import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup
from tqdm import tqdm
from config import MODEL_NAME, MAX_LEN, BATCH_SIZE, EPOCHS, LEARNING_RATE, INTENTS


# ============== BIO标签定义 ==============

BIO_TAGS = ['O', 'B-METRIC', 'I-METRIC', 'B-TIME', 'I-TIME',
            'B-DIM', 'I-DIM', 'B-DIM_VALUE', 'I-DIM_VALUE']

TAG2ID = {tag: i for i, tag in enumerate(BIO_TAGS)}
ID2TAG = {i: tag for i, tag in enumerate(BIO_TAGS)}


# ============== 数据加载 ==============

def load_ner_train_data(file_path="data/ner_train_data.json"):
    """加载NER训练数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f" Loaded {len(data)} training samples")
    return data


# ============== Dataset ==============

class JointDataset(Dataset):
    def __init__(self, data, tokenizer, max_len=MAX_LEN):
        self.data = data
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.label2id = {label: i for i, label in enumerate(INTENTS)}

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        text = item['text']
        label = item['label']
        bio_tags = item['bio_tags']

        # Tokenize
        encoding = self.tokenizer(
            text,
            max_length=self.max_len,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        input_ids = encoding['input_ids'].squeeze()
        attention_mask = encoding['attention_mask'].squeeze()

        # Align BIO tags with tokens
        token_bio_ids = self._align_bio_tags(text, bio_tags, encoding)

        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'intent_label': torch.tensor(self.label2id[label], dtype=torch.long),
            'bio_labels': torch.tensor(token_bio_ids, dtype=torch.long)
        }

    def _align_bio_tags(self, text, char_bio_tags, encoding):
        """将字符级别的BIO标签对齐到token级别"""
        tokens = self.tokenizer.convert_ids_to_tokens(encoding['input_ids'].squeeze())
        token_bio_ids = [TAG2ID['O']] * self.max_len

        # 简单的字符到token映射
        char_to_tokens = self._get_char_to_token_map(text, tokens)

        for char_idx, bio_tag in enumerate(char_bio_tags):
            if char_idx < len(char_to_tokens):
                token_indices = char_to_tokens[char_idx]
                if isinstance(token_indices, list):
                    for ti in token_indices:
                        if ti < self.max_len:
                            token_bio_ids[ti] = TAG2ID.get(bio_tag, TAG2ID['O'])
                elif token_indices < self.max_len:
                    token_bio_ids[token_indices] = TAG2ID.get(bio_tag, TAG2ID['O'])

        return token_bio_ids

    def _get_char_to_token_map(self, text, tokens):
        """获取每个字符对应的token索引列表"""
        char_to_tokens = [[] for _ in range(len(text))]
        current_char = 0

        for i, token in enumerate(tokens):
            if i == 0:  # Skip [CLS]
                continue
            if i >= self.max_len - 1:  # Skip [SEP] and padding
                break
            if current_char >= len(text):
                break

            if token in ['[PAD]', '[SEP]', '[CLS]']:
                continue

            if token.startswith('##') or token.startswith('▁'):
                subword_token = token.lstrip('##▁')
                if current_char < len(text) and text[current_char] == subword_token[0]:
                    char_to_tokens[current_char].append(i)
                    current_char += 1
                    while current_char < len(text) and subword_token.startswith(text[current_char]):
                        char_to_tokens[current_char].append(i)
                        current_char += 1
                        subword_token = subword_token[len(text[current_char-1]):]
                        if not subword_token:
                            break
            else:
                if current_char < len(text):
                    char_to_tokens[current_char].append(i)
                    current_char += 1

        return char_to_tokens


# ============== 模型 ==============

class JointBERTModel(nn.Module):
    def __init__(self, model_name, num_intents, num_ner_tags, dropout=0.1, state_dict_path=None):
        super().__init__()
        # Load BERT from the original pretrained model
        self.bert = AutoModel.from_pretrained(model_name, local_files_only=True)
        self.hidden_size = self.bert.config.hidden_size

        self.intent_dropout = nn.Dropout(dropout)
        self.intent_classifier = nn.Linear(self.hidden_size, num_intents)

        self.ner_dropout = nn.Dropout(dropout)
        self.ner_classifier = nn.Linear(self.hidden_size, num_ner_tags)

        # If state_dict_path is provided, load the trained state dict
        if state_dict_path:
            state_dict = torch.load(state_dict_path, map_location='cpu')
            self.load_state_dict(state_dict)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        sequence_output = outputs.last_hidden_state
        pooled_output = outputs.pooler_output

        intent_logits = self.intent_classifier(self.intent_dropout(pooled_output))
        ner_logits = self.ner_classifier(self.ner_dropout(sequence_output))

        return {
            'intent_logits': intent_logits,
            'ner_logits': ner_logits
        }


# ============== 训练 ==============

def train_joint_model():
    print("="*60)
    print("联合训练：意图分类 + NER")
    print("="*60)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n设备: {device}")

    # 加载数据
    train_data = load_ner_train_data("data/ner_train_data_clean.json")

    # 划分训练集和验证集
    np.random.seed(42)
    indices = np.random.permutation(len(train_data))
    split = int(len(train_data) * 0.9)
    train_indices = indices[:split]
    val_indices = indices[split:]

    train_dataset = [train_data[i] for i in train_indices]
    val_dataset = [train_data[i] for i in val_indices]

    print(f"训练集: {len(train_dataset)} 条")
    print(f"验证集: {len(val_dataset)} 条")

    # 加载tokenizer
    print("\n 加载tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, local_files_only=True)

    # 创建数据集
    train_ds = JointDataset(train_dataset, tokenizer)
    val_ds = JointDataset(val_dataset, tokenizer)

    # 创建DataLoader
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, num_workers=0)

    # 加载模型
    print("\n 加载预训练模型...")
    model = JointBERTModel(
        model_name=MODEL_NAME,
        num_intents=len(INTENTS),
        num_ner_tags=len(BIO_TAGS)
    )
    model.to(device)

    # 优化器和调度器
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=0.01)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=total_steps // 10,
        num_training_steps=total_steps
    )

    # 损失函数
    intent_loss_fct = nn.CrossEntropyLoss()
    ner_loss_fct = nn.CrossEntropyLoss(ignore_index=-100)

    # 训练循环
    print("\n 开始训练...")
    print("="*60)

    best_val_acc = 0
    intent_weight = 1.0
    ner_weight = 1.0

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{EPOCHS}")

        for batch in progress_bar:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            intent_labels = batch['intent_label'].to(device)
            bio_labels = batch['bio_labels'].to(device)

            optimizer.zero_grad()

            outputs = model(input_ids, attention_mask)

            # Intent loss
            intent_loss = intent_loss_fct(outputs['intent_logits'], intent_labels)

            # NER loss
            ner_logits = outputs['ner_logits']
            ner_loss = ner_loss_fct(
                ner_logits.view(-1, ner_logits.size(-1)),
                bio_labels.view(-1)
            )

            # Combined loss
            loss = intent_weight * intent_loss + ner_weight * ner_loss

            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})

        avg_train_loss = total_loss / len(train_loader)

        # 验证
        model.eval()
        val_correct = 0
        val_total = 0
        val_ner_correct = 0
        val_ner_total = 0

        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                intent_labels = batch['intent_label'].to(device)
                bio_labels = batch['bio_labels'].to(device)

                outputs = model(input_ids, attention_mask)

                # Intent accuracy
                preds = torch.argmax(outputs['intent_logits'], dim=1)
                val_correct += (preds == intent_labels).sum().item()
                val_total += intent_labels.size(0)

                # NER accuracy
                ner_preds = torch.argmax(outputs['ner_logits'], dim=2)
                # 计算非padding的准确率
                mask = bio_labels != -100
                val_ner_correct += ((ner_preds == bio_labels) & mask).sum().item()
                val_ner_total += mask.sum().item()

        val_acc = val_correct / val_total if val_total > 0 else 0
        val_ner_acc = val_ner_correct / val_ner_total if val_ner_total > 0 else 0

        print(f"\nEpoch {epoch+1}/{EPOCHS}")
        print(f"  Train Loss: {avg_train_loss:.4f}")
        print(f"  Val Intent Acc: {val_acc:.4f}")
        print(f"  Val NER Acc: {val_ner_acc:.4f}")

        # 保存最佳模型
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            print(f"   保存最佳模型 (acc={val_acc:.4f})")

            save_dir = "best_model/joint_v2"
            os.makedirs(save_dir, exist_ok=True)

            try:
                # 1. 先保存模型权重到临时文件，再rename（原子写入，防止损坏）
                temp_model_path = os.path.join(save_dir, "pytorch_model_temp.bin")
                torch.save(model.state_dict(), temp_model_path)
                final_model_path = os.path.join(save_dir, "pytorch_model.bin")
                if os.path.exists(final_model_path):
                    os.remove(final_model_path)
                os.rename(temp_model_path, final_model_path)

                # 2. 保存tokenizer
                tokenizer.save_pretrained(save_dir)

                # 3. 保存标签映射
                tag_mapping = {
                    'bio_tags': BIO_TAGS,
                    'tag2id': TAG2ID,
                    'id2tag': {int(k): v for k, v in ID2TAG.items()},
                    'intents': INTENTS,
                    'intent2id': {i: label for i, label in enumerate(INTENTS)},
                    'id2intent': {i: label for i, label in enumerate(INTENTS)}
                }
                temp_tag_path = os.path.join(save_dir, "tag_mapping_temp.json")
                with open(temp_tag_path, 'w', encoding='utf-8') as f:
                    json.dump(tag_mapping, f, ensure_ascii=False, indent=2)
                final_tag_path = os.path.join(save_dir, "tag_mapping.json")
                if os.path.exists(final_tag_path):
                    os.remove(final_tag_path)
                os.rename(temp_tag_path, final_tag_path)

                print(f"   模型保存成功!")

            except Exception as save_err:
                print(f"   保存失败: {save_err}")
                import traceback
                traceback.print_exc()

    print("\n 训练完成!")
    print(f"最佳验证准确率: {best_val_acc:.4f}")
    print(f"新模型保存在: best_model/joint_v2/")
    print(f"替换旧模型命令: 将 best_model/joint_v2/ 下的文件复制到 best_model/joint/")

    return model


if __name__ == "__main__":
    try:
        model = train_joint_model()
    except Exception as e:
        print(f"\n 训练出错: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
